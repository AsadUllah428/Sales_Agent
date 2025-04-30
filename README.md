# Sales Agent

This project implements a command-line sales agent that can interact with users, collect their information, store it in a CSV file, and automatically follow up with leads. It leverages the Google ADK (Agent Development Kit) for building the conversational agent and includes robust state management and thread-safe file operations.

## Overview

The Sales Agent guides users through a simple information-gathering process, including their name, consent to be asked questions, age, country, and product/service interest. This information is persisted in a CSV file. A background follow-up mechanism periodically checks for inactive leads and sends them a follow-up message to re-engage.

## Key Features

* **Interactive Command-Line Interface:** Engage with the sales agent directly from your terminal.
* **State Management:** The agent maintains the conversation flow and user information using session states.
* **Lead Tracking:** User interactions and collected data are stored in a CSV file (`leads.csv` by default).
* **Automatic Follow-Up:** A background thread automatically sends follow-up messages to active leads after a defined period of inactivity.
* **Configurable:** Settings like the CSV filename, follow-up intervals, and logging levels can be configured via a `.env` file.
* **Thread-Safe Data Management:** The `DataManager` class ensures safe reading and writing to the CSV file, even with the background follow-up process.
* **Logging:** Comprehensive logging helps in monitoring and debugging the application.

## Prerequisites

* **Python 3.6 or higher**
* **pip** (Python package installer)
* **Google Cloud Credentials (Optional):** If you plan to integrate with more advanced Google Cloud services in the future, you might need to set up Google Cloud credentials. The application currently looks for a `sales-agents-458107-640159d1d5a2.json` file or the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

## Installation

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: You might need to create a `requirements.txt` file listing dependencies like `python-dotenv` and `google-generativeai` or `google-adk` if you haven't already.)*

2.  **Configure environment variables (optional):**
    Create a `.env` file in the project root to customize settings. Example:
    ```
    CSV_FILENAME=sales_leads.csv
    APP_NAME=my_sales_app
    SIMULATED_DELAY_SECONDS=5
    FOLLOW_UP_CHECK_INTERVAL_SECONDS=120
    GOOGLE_CREDENTIALS_PATH=/path/to/your/credentials.json
    LOG_LEVEL=DEBUG
    LOG_FILE=agent.log
    ```
    If you don't create a `.env` file, the application will use the default values defined in `config.py`.

## Usage

Run the `main.py` script from your terminal:

```bash
python main.py
