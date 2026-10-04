import json
from functools import lru_cache # Least Recent Used - Returns cached dictionary from the path
import logging
from pathlib import Path

from requests import api

CONFIG_FILE= 'config.json'
RECOMMENDATIONS_FILE = 'recommendations.json'
APP_DIR = Path(__file__).resolve().parent
api_config_path = APP_DIR / CONFIG_FILE
recommendations_config_path = APP_DIR / RECOMMENDATIONS_FILE

try:
    with api_config_path.open(encoding="utf-8") as api_file:
        API_CONFIG = json.load(api_file)
    logging.info("Configs loaded")
except FileNotFoundError as exc:
    logging.error('API configuration file not found')
    raise FileNotFoundError(f"API configuration file not found. {api_config_path} is missing")
except Exception as exc:
    logging.error(f"{type(exc).__name__}: {str(exc)}")
    print(f"{type(exc).__name__}: {str(exc)}")


try:
    with recommendations_config_path.open(encoding="utf-8") as recommendations_file:
        RECOMMENDATIONS = json.load(recommendations_file)
    print("Recommendations loaded")
except FileNotFoundError as exc:
    logging.error(f"{exc}: Recommendations file file not found")
    raise FileNotFoundError(f"Recommendations file file not found. {recommendations_config_path} is missing")
except Exception as exc:
    logging.error(f"{type(exc).__name__}: {str(exc)}")
    print(f"{type(exc).__name__}: {str(exc)}")