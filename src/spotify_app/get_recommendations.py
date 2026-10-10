import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from requests import Response, get
from requests.exceptions import RequestException

from spotify_app.config import (
    API_CONFIG,
    PAYLOADS_FOLDER_PATH,
    PROJECT_ROOT,
    get_api_key,
)


MOODS_PAYLOAD_PATH = (
    PROJECT_ROOT / "src" / "spotify_app" / "moods_payload.json"
)
PAYLOADS_DIR = PAYLOADS_FOLDER_PATH / "recommendations"
API_HOST = API_CONFIG["URL"]
RECOMMENDATIONS_ENDPOINT = API_CONFIG["RECOMMENDATIONS"]
RECOMMENDATIONS_URL = f"https://{API_HOST}{RECOMMENDATIONS_ENDPOINT}"


def load_mood_payloads() -> dict[str, dict]:
    with MOODS_PAYLOAD_PATH.open(encoding="utf-8") as payload_file:
        payloads = json.load(payload_file)

    if not isinstance(payloads, dict):
        raise ValueError("Mood payloads must be a JSON object")

    if len(payloads) != 10:
        raise ValueError(
            f"Expected 10 mood payloads, found {len(payloads)}",
        )

    for mood_name, parameters in payloads.items():
        if not isinstance(mood_name, str) or not mood_name:
            raise ValueError("Every mood must have a non-empty name")

        if not isinstance(parameters, dict):
            raise ValueError(
                f"Payload for {mood_name} must be a JSON object",
            )

        seed_genres = parameters.get("seed_genres")
        if not isinstance(seed_genres, str):
            raise ValueError(
                f"{mood_name} must define seed_genres as a string",
            )

        genres = [
            genre.strip()
            for genre in seed_genres.split(",")
            if genre.strip()
        ]

        if len(genres) != 5:
            raise ValueError(
                f"{mood_name} must contain exactly five genre seeds",
            )

    return payloads


def fetch_recommendations(api_key: str, parameters: dict) -> Response:
    headers = {
        "x-rapidapi-host": API_HOST,
        "x-rapidapi-key": api_key,
    }

    return get(
        RECOMMENDATIONS_URL,
        headers=headers,
        params=parameters,
        timeout=30,
    )


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as output_file:
        json.dump(
            value,
            output_file,
            indent=2,
            ensure_ascii=False,
        )
        output_file.write("\n")


def save_raw_response(
    response: Response,
    output_directory: Path,
    mood_name: str,
) -> Path:
    content_type = response.headers.get("content-type", "").lower()

    if "json" in content_type:
        suffix = ".response.json"
    else:
        suffix = ".response.txt"

    response_path = output_directory / f"{mood_name}{suffix}"
    response_path.write_bytes(response.content)

    return response_path


def acquire_mood(
    mood_name: str,
    parameters: dict,
    api_key: str,
    output_directory: Path,
) -> None:
    requested_at = datetime.now(UTC).isoformat()

    request_record = {
        "mood": mood_name,
        "endpoint": RECOMMENDATIONS_URL,
        "requested_at": requested_at,
        "parameters": parameters,
    }

    write_json(
        output_directory / f"{mood_name}.request.json",
        request_record,
    )

    try:
        response = fetch_recommendations(
            api_key=api_key,
            parameters=parameters,
        )
    except RequestException as error:
        failure_record = {
            "mood": mood_name,
            "requested_at": requested_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "status": "request_failed",
            "error_type": type(error).__name__,
            "error": str(error),
        }

        write_json(
            output_directory / f"{mood_name}.result.json",
            failure_record,
        )

        logging.error("%s failed: %s", mood_name, error)
        return

    response_path = save_raw_response(
        response=response,
        output_directory=output_directory,
        mood_name=mood_name,
    )

    result_record = {
        "mood": mood_name,
        "requested_at": requested_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "status": "succeeded" if response.ok else "http_error",
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "response_file": response_path.name,
    }

    write_json(
        output_directory / f"{mood_name}.result.json",
        result_record,
    )

    if response.ok:
        logging.info(
            "%s saved to %s",
            mood_name,
            response_path,
        )
    else:
        logging.error(
            "%s returned HTTP %s",
            mood_name,
            response.status_code,
        )


def main() -> None:
    api_key = get_api_key()
    mood_payloads = load_mood_payloads()

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_directory = PAYLOADS_DIR / run_id
    output_directory.mkdir(parents=True, exist_ok=True)

    logging.info(
        "Starting acquisition run %s with %s payloads",
        run_id,
        len(mood_payloads),
    )

    for mood_name, parameters in mood_payloads.items():
        acquire_mood(
            mood_name=mood_name,
            parameters=parameters,
            api_key=api_key,
            output_directory=output_directory,
        )

    logging.info(
        "Acquisition run finished: %s",
        output_directory,
    )


if __name__ == "__main__":
    main()
