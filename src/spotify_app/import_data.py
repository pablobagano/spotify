import json
import logging
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from spotify_app.config import PAYLOADS_FOLDER_PATH
from spotify_app.database import database


RECOMMENDATIONS_DIR = PAYLOADS_FOLDER_PATH / "recommendations"
RESPONSE_STATUSES = {"succeeded", "http_error", "request_failed"}


def load_payload(filename: str) -> object:
    payload_path = PAYLOADS_FOLDER_PATH / filename

    if not payload_path.is_file():
        raise FileNotFoundError(f"Payload not found: {payload_path}")

    return read_json(payload_path)


def read_json(path: Path) -> object:
    with path.open(encoding="utf-8") as payload_file:
        return json.load(payload_file)


def import_genres() -> None:
    payload = load_payload("available_genre_seeds.json")

    if not isinstance(payload, dict):
        raise ValueError("Genre payload must be a JSON object")

    genres = payload.get("genres")

    if not isinstance(genres, list):
        raise ValueError("Genre payload must contain a genres list")

    if not all(isinstance(genre, str) and genre for genre in genres):
        raise ValueError("Every genre must be a non-empty string")

    rows = [(genre,) for genre in genres]

    with database.transaction() as connection:
        connection.executemany(
            """
            INSERT INTO genres (name)
            VALUES (?)
            ON CONFLICT(name) DO UPDATE SET
                enabled = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            rows,
        )

    logging.info("Imported %s genres", len(rows))


def latest_run_directory() -> Path:
    run_directories = sorted(
        path for path in RECOMMENDATIONS_DIR.iterdir() if path.is_dir()
    )

    if not run_directories:
        raise FileNotFoundError(
            f"No recommendation runs found in {RECOMMENDATIONS_DIR}",
        )

    return run_directories[-1]


def split_seed_genres(seed_genres: str) -> list[str]:
    return [
        genre.strip()
        for genre in seed_genres.split(",")
        if genre.strip()
    ]


def load_mood_records(run_directory: Path) -> list[dict]:
    request_paths = sorted(run_directory.glob("*.request.json"))

    if not request_paths:
        raise FileNotFoundError(
            f"No request files found in {run_directory}",
        )

    records = []

    for request_path in request_paths:
        mood_name = request_path.name.removesuffix(".request.json")
        result_path = run_directory / f"{mood_name}.result.json"

        if not result_path.is_file():
            raise FileNotFoundError(f"Result file not found: {result_path}")

        request = read_json(request_path)
        result = read_json(result_path)

        if not isinstance(request, dict) or not isinstance(result, dict):
            raise ValueError(
                f"{mood_name} request and result must be JSON objects",
            )

        if request.get("mood") != mood_name or result.get("mood") != mood_name:
            raise ValueError(f"{mood_name} files disagree on the mood name")

        parameters = request.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError(f"{mood_name} request must contain parameters")

        seed_genres = parameters.get("seed_genres")
        if not isinstance(seed_genres, str):
            raise ValueError(f"{mood_name} must define seed_genres")

        status = result.get("status")
        if status not in RESPONSE_STATUSES:
            raise ValueError(f"{mood_name} has unknown status {status!r}")

        response = None
        if status == "succeeded":
            response_path = run_directory / result["response_file"]
            response = read_json(response_path)
            validate_response(
                mood_name=mood_name,
                response=response,
                seed_genres=split_seed_genres(seed_genres),
            )

        records.append(
            {
                "mood": mood_name,
                "request": request,
                "result": result,
                "seed_genres": split_seed_genres(seed_genres),
                "response": response,
            },
        )

    return records


def validate_response(
    mood_name: str,
    response: object,
    seed_genres: list[str],
) -> None:
    if not isinstance(response, dict):
        raise ValueError(f"{mood_name} response must be a JSON object")

    seeds = response.get("seeds")
    tracks = response.get("tracks")

    if not isinstance(seeds, list) or not isinstance(tracks, list):
        raise ValueError(f"{mood_name} response must contain seeds and tracks")

    if any(seed.get("type") != "genre" for seed in seeds):
        raise ValueError(f"{mood_name} response contains non-genre seeds")

    response_genres = {seed.get("id") for seed in seeds}
    if response_genres != set(seed_genres):
        raise ValueError(
            f"{mood_name} response seeds do not match the request seeds",
        )

    track_ids = set()

    for track in tracks:
        track_id = track.get("id")

        if not isinstance(track_id, str) or not track_id:
            raise ValueError(f"{mood_name} contains a track without an id")

        if track.get("uri") != f"spotify:track:{track_id}":
            raise ValueError(f"{mood_name} track {track_id} has a bad URI")

        if not track.get("name"):
            raise ValueError(f"{mood_name} track {track_id} has no name")

        if track_id in track_ids:
            raise ValueError(f"{mood_name} returns track {track_id} twice")

        track_ids.add(track_id)

        artists = track.get("artists")
        if not isinstance(artists, list) or not artists:
            raise ValueError(f"{mood_name} track {track_id} has no artists")

        for artist in artists:
            if not artist.get("id") or not artist.get("name"):
                raise ValueError(
                    f"{mood_name} track {track_id} has an invalid artist",
                )


def release_year(album: dict) -> int | None:
    release_date = album.get("release_date") or ""

    if len(release_date) >= 4 and release_date[:4].isdigit():
        return int(release_date[:4])

    return None


def lookup_genre_ids(
    connection: sqlite3.Connection,
    records: list[dict],
) -> dict[str, int]:
    names = sorted(
        {genre for record in records for genre in record["seed_genres"]},
    )
    placeholders = ",".join("?" for _ in names)

    rows = connection.execute(
        f"SELECT id, name FROM genres WHERE name IN ({placeholders})",
        names,
    ).fetchall()
    genre_ids = {row["name"]: row["id"] for row in rows}

    missing = [name for name in names if name not in genre_ids]
    if missing:
        raise ValueError(
            "Seed genres missing from the genres table "
            f"(run import_genres first): {', '.join(missing)}",
        )

    return genre_ids


def upsert_run(
    connection: sqlite3.Connection,
    run_key: str,
    records: list[dict],
) -> int:
    provider = urlparse(records[0]["request"]["endpoint"]).hostname
    started_at = min(record["request"]["requested_at"] for record in records)
    finished_at = max(
        record["result"].get("finished_at") or "" for record in records
    )
    succeeded_count = sum(
        record["result"]["status"] == "succeeded" for record in records
    )

    connection.execute(
        """
        INSERT INTO acquisition_runs (
            run_key, provider, started_at, finished_at,
            requested_count, succeeded_count, failed_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_key) DO UPDATE SET
            provider = excluded.provider,
            started_at = excluded.started_at,
            finished_at = excluded.finished_at,
            requested_count = excluded.requested_count,
            succeeded_count = excluded.succeeded_count,
            failed_count = excluded.failed_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            run_key,
            provider,
            started_at,
            finished_at or None,
            len(records),
            succeeded_count,
            len(records) - succeeded_count,
        ),
    )

    return connection.execute(
        "SELECT id FROM acquisition_runs WHERE run_key = ?",
        (run_key,),
    ).fetchone()["id"]


def upsert_request(
    connection: sqlite3.Connection,
    run_id: int,
    record: dict,
) -> int:
    request = record["request"]
    result = record["result"]

    connection.execute(
        """
        INSERT INTO acquisition_requests (
            acquisition_run_id, mood, endpoint, request_parameters,
            requested_at, finished_at, response_status, status_code,
            content_type, response_file, error_type, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(acquisition_run_id, mood) DO UPDATE SET
            endpoint = excluded.endpoint,
            request_parameters = excluded.request_parameters,
            requested_at = excluded.requested_at,
            finished_at = excluded.finished_at,
            response_status = excluded.response_status,
            status_code = excluded.status_code,
            content_type = excluded.content_type,
            response_file = excluded.response_file,
            error_type = excluded.error_type,
            error = excluded.error
        """,
        (
            run_id,
            record["mood"],
            request["endpoint"],
            json.dumps(request["parameters"], ensure_ascii=False),
            request["requested_at"],
            result.get("finished_at"),
            result["status"],
            result.get("status_code"),
            result.get("content_type"),
            result.get("response_file"),
            result.get("error_type"),
            result.get("error"),
        ),
    )

    return connection.execute(
        """
        SELECT id FROM acquisition_requests
        WHERE acquisition_run_id = ? AND mood = ?
        """,
        (run_id, record["mood"]),
    ).fetchone()["id"]


def upsert_track(connection: sqlite3.Connection, track: dict) -> int:
    album = track.get("album") or {}
    external_ids = track.get("external_ids") or {}

    connection.execute(
        """
        INSERT INTO tracks (
            spotify_track_id, spotify_uri, title, release_year, isrc,
            album_name, spotify_album_id, explicit, popularity
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(spotify_track_id) DO UPDATE SET
            spotify_uri = excluded.spotify_uri,
            title = excluded.title,
            release_year = excluded.release_year,
            isrc = excluded.isrc,
            album_name = excluded.album_name,
            spotify_album_id = excluded.spotify_album_id,
            explicit = excluded.explicit,
            popularity = excluded.popularity,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            track["id"],
            track["uri"],
            track["name"],
            release_year(album),
            external_ids.get("isrc"),
            album.get("name"),
            album.get("id"),
            int(track["explicit"]) if "explicit" in track else None,
            track.get("popularity"),
        ),
    )

    return connection.execute(
        "SELECT id FROM tracks WHERE spotify_track_id = ?",
        (track["id"],),
    ).fetchone()["id"]


def upsert_artist(connection: sqlite3.Connection, artist: dict) -> int:
    connection.execute(
        """
        INSERT INTO artists (spotify_artist_id, name)
        VALUES (?, ?)
        ON CONFLICT(spotify_artist_id) DO UPDATE SET
            name = excluded.name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (artist["id"], artist["name"]),
    )

    return connection.execute(
        "SELECT id FROM artists WHERE spotify_artist_id = ?",
        (artist["id"],),
    ).fetchone()["id"]


def import_recommendations(run_directory: Path | None = None) -> None:
    run_directory = run_directory or latest_run_directory()
    records = load_mood_records(run_directory)

    with database.transaction() as connection:
        genre_ids = lookup_genre_ids(connection, records)
        run_id = upsert_run(connection, run_directory.name, records)

        for record in records:
            request_id = upsert_request(connection, run_id, record)

            connection.executemany(
                """
                INSERT OR IGNORE INTO acquisition_request_genres (
                    acquisition_request_id, genre_id
                )
                VALUES (?, ?)
                """,
                [
                    (request_id, genre_ids[genre])
                    for genre in record["seed_genres"]
                ],
            )

            if record["response"] is None:
                continue

            for position, track in enumerate(record["response"]["tracks"]):
                track_id = upsert_track(connection, track)

                for artist_position, artist in enumerate(track["artists"]):
                    artist_id = upsert_artist(connection, artist)
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO track_artists (
                            track_id, artist_id, position, is_primary
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            track_id,
                            artist_id,
                            artist_position,
                            int(artist_position == 0),
                        ),
                    )

                connection.execute(
                    """
                    INSERT OR IGNORE INTO acquisition_request_tracks (
                        acquisition_request_id, track_id, position
                    )
                    VALUES (?, ?, ?)
                    """,
                    (request_id, track_id, position),
                )

    track_count = sum(
        len(record["response"]["tracks"])
        for record in records
        if record["response"] is not None
    )
    logging.info(
        "Imported run %s: %s requests, %s track occurrences",
        run_directory.name,
        len(records),
        track_count,
    )


def main() -> None:
    import_genres()
    import_recommendations()


if __name__ == "__main__":
    main()
