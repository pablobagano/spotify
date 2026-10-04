from json import dump
import os
import logging
from pathlib import Path

from requests import get
from dotenv import load_dotenv

from spotify_app.config import API_CONFIG



PROJECT_ROOT = Path(__file__).resolve().parents[2]


API_HOST = API_CONFIG["URL"]
GENRES = API_CONFIG["GENRES"]
GENRES_URL = f"https://{API_HOST}{GENRES}"

def get_api_key():
    load_dotenv()

    api_key = os.getenv("RAPID_API_KEY")
    if not api_key:
        raise RuntimeError("RAPID_API_KEY is not configured")
    
    return api_key


def fetch_genres(api_key: str) -> object:
    headers = {
        "x-rapidapi-host": API_HOST,
        "x-rapidapi-key": api_key,
    }

    response = get(
        GENRES_URL,
        headers=headers,
        timeout=30
    )
    response.raise_for_status()

    payload = response.json()
    
    return payload




PAYLOADS_FOLDER_PATH = (
    PROJECT_ROOT
    / "data"
    / "payload"
)
GENRES_PAYLOAD_PATH = PAYLOADS_FOLDER_PATH / "available_genre_seeds.json"

def save_payload(payload: object) -> None:
    GENRES_PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)

    with GENRES_PAYLOAD_PATH.open("w", encoding="utf-8") as output_file:
        dump(payload, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")



def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    api_key = get_api_key()
    payload = fetch_genres(api_key)
    save_payload(payload)

    logging.info(
        f"Genres payload saved to {GENRES_PAYLOAD_PATH}",
    )


if __name__ == "__main__":
    main()
