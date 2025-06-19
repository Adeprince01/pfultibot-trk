# 🚀 Telegram Crypto Call Tracker

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports Style](https://img.shields.io/badge/imports-isort-ef8336.svg)](https://pycqa.github.io/isort/)
[![Types](https://img.shields.io/badge/types-mypy-blue.svg)](http://mypy-lang.org/)

A sophisticated Python application that monitors Telegram channels for cryptocurrency trading calls, parses them in real-time, enriches the data, and stores it in multiple backends for robust analysis.

## ✨ Key Features

- **Advanced Message Linking**: Automatically connects update messages (e.g., "2.5x gain") to their original "discovery" calls using Telegram's reply system, ensuring perfect data attribution.
- **Real-time Monitoring**: Listens to specified Telegram channels 24/7 for live crypto calls.
- **Intelligent Parsing**: Extracts key data points like token name, contract address, entry market cap, peak market cap, and X-gain multipliers.
- **Multi-Storage Support**: Persists data simultaneously to SQLite, Excel, and Google Sheets.
- **Resilient Architecture**: Built for continuous operation with graceful error handling, connection retries, and detailed logging.
- **Data Integrity**: Uses a SQLite database with a structured schema (`raw_messages`, `crypto_calls`) to ensure data is clean and linked correctly.
- **In-depth Analysis**: Includes scripts to analyze the collected data, showing token performance, win rates, and more.
- **Secure**: Follows best practices by loading all secrets and configurations from an `.env` file.

## 🏛️ Architecture

The application is built with a modular and scalable architecture:

-   `monitor.py`: The main entry point for the production application. It orchestrates the listener and storage components.
-   `src/listener.py`: Handles the connection to Telegram, listens for new messages, and passes them to the parser.
-   `src/parser.py`: Contains the logic for parsing different types of messages (discovery, update, bonding curve) and extracting structured data.
-   `src/storage/`: A package with different storage backends.
    -   `sqlite.py`: Manages the SQLite database, the primary data store.
    -   `excel.py`: Manages writing data to an `.xlsx` file.
    -   `sheet.py`: Manages writing data to Google Sheets.
    -   `multi.py`: A wrapper that coordinates writing to all enabled backends.
-   `src/settings.py`: Manages all application settings loaded from the `.env` file using Pydantic.
-   `analyze_database.py`: A script for running and viewing analytics on the collected data.

## 🚀 Getting Started

Follow these steps to get the bot up and running.

### 1. Prerequisites

-   Python 3.11+
-   A Telegram account with API credentials.

### 2. Installation

```bash
# Clone the repository
git clone <repository_url>
cd pfultibot-trk

# Create and activate a virtual environment
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

### 3. Configuration

The application uses an `.env` file for configuration.

```bash
# Create the .env file by copying the example
copy env.example .env
```

Now, open the `.env` file and fill in your details:

```dotenv
# --- Telegram API Credentials (Required) ---
API_ID=...
API_HASH=...

# --- Telegram Session (Required) ---
# The name for the .session file that Telethon will create
TG_SESSION="pf_session"

# --- Optional: Storage Configuration ---
# Set to true to enable a storage backend

# Excel Storage
ENABLE_EXCEL=false
EXCEL_PATH="crypto_calls.xlsx"

# Google Sheets Storage
ENABLE_SHEETS=false
SHEET_ID="..."
GOOGLE_CREDENTIALS_PATH="credentials.json"
```

### 4. First-Time Authentication

Before running the monitor for the first time, you need to authorize the application with your Telegram account.

```bash
python authenticate_telegram.py
```

You will be prompted to enter your phone number, a code sent to you on Telegram, and your 2FA password if you have one. This will create a `.session` file (named according to `TG_SESSION` in your `.env`) so you don't have to log in again.

## 🛠️ Usage

### Running the Monitor

To start listening for new messages and processing them, run the `monitor.py` script:

```bash
python monitor.py
```

The monitor will connect to Telegram and log its activity to both the console and a log file in the `logs/` directory.

### Analyzing the Data

To view analytics based on the data collected in the SQLite database, run `analyze_database.py`:

```bash
python analyze_database.py
```

This script provides insights into token performance, linking rates, and other useful metrics.

### Checking Database Health

You can run `check_database.py` to get a summary of the contents of your SQLite database, including counts of raw messages and processed calls.

## 📦 Storage Backends

The application can store data in multiple places simultaneously for redundancy and convenience.

-   **SQLite (Primary)**: Always enabled. It stores both raw messages and the parsed `crypto_calls`. The database file is `crypto_calls_production.db`.
-   **Excel**: Disabled by default. Set `ENABLE_EXCEL=true` in `.env` to save all parsed calls to an Excel file.
-   **Google Sheets**: Disabled by default. Set `ENABLE_SHEETS=true` and provide a `SHEET_ID` and `GOOGLE_CREDENTIALS_PATH` to save calls to a Google Sheet.

## 🧑‍💻 Development & Contribution

We use a suite of tools to maintain code quality.

-   **Formatting**: `black`
-   **Import Sorting**: `isort`
-   **Type Checking**: `mypy`
-   **Testing**: `pytest`

Before committing, please run the formatters:
```bash
black .
isort .
```

For more detailed contribution guidelines, please consult the documents referenced in `AI_REFERENCE_INDEX.md`.

## 📁 Project Structure

```
pfultibot/
├── data/                  # Data files, including the database
├── logs/                  # Log files
├── src/                   # Source code
│   ├── storage/           # Storage backends
│   ├── __init__.py
│   ├── enricher.py
│   ├── listener.py
│   ├── main.py
│   ├── metrics.py
│   ├── parser.py
│   └── settings.py
├── tests/                 # Unit and integration tests
├── .env                   # Local environment variables (gitignored)
├── env.example            # Example environment file
├── analyze_database.py    # Main analysis script
├── authenticate_telegram.py # First-time auth script
├── monitor.py             # Main application entry point
└── requirements.txt       # Python dependencies
```

</rewritten_file>