# config.py

import os

CSV_FILENAME = "leads.csv"
APP_NAME = "sales_agent_app"

# FOLLOW_UP_DELAY_HOURS = 24   # Hours (real deployment)
SIMULATED_DELAY_SECONDS = 15 
FOLLOW_UP_CHECK_INTERVAL_SECONDS = 15  

# Google Service Account (path or env)
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or os.environ.get("GOOGLE_CREDENTIALS_PATH") or "your path here"
PROJECT_ID = os.environ.get("PROJECT_ID") or "your id here"

# Logging settings
LOG_LEVEL = "INFO"  
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "sales_agent.log"   