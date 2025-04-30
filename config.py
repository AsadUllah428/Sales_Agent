# config.py


CSV_FILENAME = "leads.csv"
APP_NAME = "sales_agent_app"

# FOLLOW_UP_DELAY_HOURS = 24   # Hours (real deployment)
SIMULATED_DELAY_SECONDS = 15 
FOLLOW_UP_CHECK_INTERVAL_SECONDS = 15  

# Google Service Account (your path)
GOOGLE_CREDENTIALS_PATH = "your path here"
PROJECT_ID = "your id here"

# Logging settings
LOG_LEVEL = "INFO"  
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = "sales_agent.log"   