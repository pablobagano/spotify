import logging
from pathlib import Path

from spotify_app.database import database


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def load_schema() -> str:
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    schema = SCHEMA_PATH.read_text(encoding="utf-8").strip()

    if not schema:
        raise ValueError(f"Schema file is empty: {SCHEMA_PATH}")

    return schema


def main() -> None:
    schema = load_schema()
    database.execute_script(schema)

    logging.info("Database initialized at %s", database.path)


if __name__ == "__main__":
    main()
