from spotify_app.config import API_CONFIG, RECOMMENDATIONS

import os
from requests import get
import logging

from dotenv import load_dotenv

if load_dotenv():
    API_KEY = os.getenv('RAPID_API_KEY')
else:
    logging.error("Failed to load .env file.")
    

URL = API_CONFIG["URL"]
RECOMMENDATIONS_ENDPOINT = API_CONFIG["RECOMMENDANTIONS"]
FULL_URL = URL + RECOMMENDATIONS_ENDPOINT
# TODO: Retrieve the necessary params in the recommendations file create the body for the GET request 
# TODO: Make the request and store the results
