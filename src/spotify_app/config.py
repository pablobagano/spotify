import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

CONFIG_FILE = "config.json"
RECOMMENDATIONS_FILE = "recommendations.json"
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parents[1]
PAYLOADS_FOLDER_PATH = PROJECT_ROOT / "data" / "payload"
API_CONFIG_PATH = APP_DIR / CONFIG_FILE
RECOMMENDATIONS_CONFIG_PATH = APP_DIR / RECOMMENDATIONS_FILE

try:
    with API_CONFIG_PATH.open(encoding="utf-8") as api_file:
        API_CONFIG = json.load(api_file)
    logging.info("Configs loaded")
except FileNotFoundError as exc:
    logging.error("API configuration file not found")
    raise FileNotFoundError(
        f"API configuration file not found. {API_CONFIG_PATH} is missing",
    ) from exc
except Exception as exc:
    logging.error("%s: %s", type(exc).__name__, exc)
    raise


try:
    with RECOMMENDATIONS_CONFIG_PATH.open(
        encoding="utf-8",
    ) as recommendations_file:
        RECOMMENDATIONS = json.load(recommendations_file)
    logging.info("Recommendations loaded")
except FileNotFoundError as exc:
    logging.error("%s: Recommendations file not found", exc)
    raise FileNotFoundError(
        "Recommendations file not found. "
        f"{RECOMMENDATIONS_CONFIG_PATH} is missing",
    ) from exc
except Exception as exc:
    logging.error("%s: %s", type(exc).__name__, exc)
    raise


def get_api_key() -> str:
    load_dotenv()

    api_key = os.getenv("RAPID_API_KEY")
    if not api_key:
        raise RuntimeError("RAPID_API_KEY is not configured")

    return api_key
