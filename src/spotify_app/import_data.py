import argparse
import json
from pathlib import Path
from typing import Callable

from spotify_app.database import PROJECT_ROOT, database
from spotify_app.get_genres import PAYLOADS_FOLDER_PATH


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAYLOADS_FOLDER_PATH = PROJECT_ROOT / "data" / "payload"


def load_payload(filename: str) -> object:
    payload_path = PAYLOADS_FOLDER_PATH / filename

    if not payload_path.is_file():
        raise FileNotFoundError(f"Payload not found: {payload_path}")
    
    with payload_path.open(encoding="utf-8") as payload_file:
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
    
    print(f"Imported {len(rows)} genres")