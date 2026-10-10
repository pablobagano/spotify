import logging
from json import dump

from requests import get

from spotify_app.config import (
    API_CONFIG,
    PAYLOADS_FOLDER_PATH,
    get_api_key,
)


API_HOST = API_CONFIG["URL"]
GENRES = API_CONFIG["GENRES"]
GENRES_URL = f"https://{API_HOST}{GENRES}"


def fetch_genres(api_key: str) -> object:
    headers = {
        "x-rapidapi-host": API_HOST,
        "x-rapidapi-key": api_key,
    }

    response = get(
        GENRES_URL,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    return payload


GENRES_PAYLOAD_PATH = PAYLOADS_FOLDER_PATH / "available_genre_seeds.json"


def save_payload(payload: object) -> None:
    GENRES_PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)

    with GENRES_PAYLOAD_PATH.open("w", encoding="utf-8") as output_file:
        dump(payload, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def main() -> None:
    api_key = get_api_key()
    payload = fetch_genres(api_key)
    save_payload(payload)

    logging.info(
        "Genres payload saved to %s",
        GENRES_PAYLOAD_PATH,
    )


if __name__ == "__main__":
    main()
