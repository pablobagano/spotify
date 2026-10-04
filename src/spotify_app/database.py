import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data/spotify_catalog.db"


class Database:
    def __init__(self, path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.path = Path(path)
    
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")

        return connection
    

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()

        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
    

    def execute_script(self, sql: str) -> None:
        with self.transaction() as connection:
            connection.executescript(sql)
    

    def fetch_all(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> list[sqlite3.Row]:
        connection = self.connect()

        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def fetch_one(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> sqlite3.Row | None:
        connection = self.connect()

        try:
            return connection.execute(sql, parameters).fetchone()
        finally:
            connection.close()


database = Database()


def main() -> None:
    connection = database.connect()
    connection.close()
    print(f"Database ready at {database.path}")


if __name__ == "__main__":
    main()
