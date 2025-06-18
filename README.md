# 🚀 Telegram Crypto Call Tracker

A comprehensive Python application that monitors Telegram channels (specifically @pfultimate) for crypto trading calls, parses them automatically, and stores analytics in SQLite database.

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation & Setup](#-installation--setup)
- [Quick Start](#-quick-start)
- [Usage Guide](#-usage-guide)
- [File Structure](#-file-structure)
- [Monitoring Modes](#-monitoring-modes)
- [Multi-Storage Setup](#-multi-storage-setup)
- [Database & Analytics](#-database--analytics)
- [Troubleshooting](#-troubleshooting)
- [Maintenance](#-maintenance)
- [Advanced Configuration](#-advanced-configuration)

## 🎯 Features

- **Real-time Monitoring**: Listens to @pfultimate for live crypto calls
- **Smart Parsing**: Automatically extracts entry cap, peak cap, gains, and VIP status
- **Multiple Formats**: Supports both traditional and @pfultimate message formats
- **Multi-Storage Support**: Save to SQLite, Excel, and Google Sheets simultaneously
- **SQLite Storage**: Persistent storage with full analytics
- **Excel Export**: Automatic .xlsx file generation with formatted data
- **Google Sheets Integration**: Real-time sync to Google Sheets for collaboration
- **Production Ready**: Designed for 24/7 operation with logging and error handling
- **Analytics Dashboard**: View gains, averages, VIP calls, and trends
- **Graceful Shutdown**: Safe stopping with data preservation

## 🔧 Prerequisites

- **Python 3.11+** 
- **Telegram Account** with API credentials
- **Windows/Linux/macOS** (tested on Windows)
- **Internet Connection** for Telegram API

## 📦 Installation & Setup

### Step 1: Clone & Setup Environment

```bash
# Navigate to your desired directory
cd C:\Users\YourName\

# Clone or download project files
# (Assuming you have the pfultibot directory)
cd pfultibot

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pydantic-settings  # Required for settings
```

### Step 2: Get Telegram API Credentials

1. Visit [my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your Telegram account
3. Create a new application
4. Copy your `API_ID` and `API_HASH`

### Step 3: Create Configuration File

Copy the example configuration:
```bash
copy env.example .env
```

Then edit `.env` file in project root:

```env
# Telegram API Credentials (Required)
API_ID=your_api_id_here
API_HASH=your_api_hash_here

# Session name (Telethon will create this file)
TG_SESSION=pf_session

# Multi-Storage Configuration (Optional)
ENABLE_EXCEL=false
EXCEL_PATH=crypto_calls.xlsx
ENABLE_SHEETS=false
SHEET_ID=your_google_sheet_id_here
GOOGLE_CREDENTIALS_PATH=credentials.json
```

**⚠️ Important**: Replace `your_api_id_here` and `your_api_hash_here` with your actual credentials.

### Step 4: Authenticate with Telegram

```bash
python authenticate_telegram.py
```

**What happens:**
- Enter your phone number (with country code): `+1234567890`
- Check Telegram app for verification code
- Enter the 5-digit code
- If you have 2FA, enter your password
- ✅ Session saved for future use

## 🏃‍♂️ Quick Start

### Option 1: Test Everything First
```bash
# Test parser with sample messages
python test_integration.py
# Choose option 1 for parser testing
# Choose option 2 for live Telegram connection
```

### Option 2: Start Production Monitoring
```bash
# Basic monitoring (SQLite only)
python crypto_monitor.py

# Enhanced monitoring (multi-storage)
python crypto_monitor_enhanced.py

# Or use Windows startup script
start_monitor.bat
```

### Option 3: Find Channel IDs (if needed)
```bash
python find_channels.py
```

## 📖 Usage Guide

### 🎧 Live Monitoring

**Start the production monitor:**
```bash
python crypto_monitor.py
```

**What you'll see:**
```
🎧 CRYPTO CALL MONITOR - RUNNING
============================================================
📢 Monitoring: @pfultimate  
💾 Database: crypto_calls_production.db
📝 Logs: logs/crypto_monitor.log
🛑 Stop: Press Ctrl+C
============================================================

🚀 CRYPTO CALL DETECTED #1
   Token: SUNSET
   Entry: $53,300
   Peak: $91,400
   Gain: 1.7x (VIP: 3.8x)
   Time: 13:24:15
--------------------------------------------------
```

**To stop safely:** Press `Ctrl+C` (graceful shutdown preserves all data)

### 📊 View Collected Data

```bash
python view_database.py
```

**Options:**
1. View parsed crypto calls (formatted)
2. View raw database info (debugging)
3. Exit

**Sample output:**
```
📊 CRYPTO CALLS DATABASE - 5 records found
===============================================================================

🚀 CALL #1
   Token: SUNSET
   Entry Cap: $53,300
   Peak Cap: $91,400
   Gain: 1.7x
   VIP: 3.8x
   Channel: Pumpfun Ultimate Alert
   Time: 13:24:15

📈 SUMMARY:
   Total Calls: 5
   Average Gain: 3.2x
   Max Gain: 8.5x
   VIP Calls: 3
```

## 📁 File Structure

```
pfultibot/
├── 📄 Core Application
│   ├── src/
│   │   ├── listener.py          # Telegram connection & message handling
│   │   ├── parser.py            # Message parsing logic  
│   │   ├── settings.py          # Configuration management
│   │   ├── storage/
│   │   │   ├── sqlite.py        # SQLite database operations
│   │   │   ├── excel.py         # Excel export functionality
│   │   │   ├── sheet.py         # Google Sheets integration
│   │   │   └── multi.py         # Multi-storage coordinator
│   │   └── main.py              # Application orchestrator
│   │
├── 🧪 Testing & Setup
│   ├── authenticate_telegram.py # One-time Telegram setup
│   ├── find_channels.py        # Find channel IDs
│   ├── test_integration.py     # Full integration testing
│   ├── test_real_message.py    # Parser testing
│   └── view_database.py        # Database viewer
│   │
├── 🚀 Production
│   ├── crypto_monitor.py        # Basic production monitoring script
│   ├── crypto_monitor_enhanced.py # Enhanced multi-storage monitoring
│   ├── start_monitor.bat        # Windows startup script
│   │
├── 📊 Data & Logs
│   ├── crypto_calls_production.db  # Production database
│   ├── test_crypto_calls.db        # Test database  
│   ├── logs/
│   │   └── crypto_monitor.log      # Application logs
│   │
├── ⚙️ Configuration
│   ├── .env                     # API credentials (create this)
│   ├── requirements.txt         # Python dependencies
│   ├── pyproject.toml          # Project configuration
│   └── README.md               # This file
│
└── 📚 Documentation
    ├── PROJECT_PLAN.md         # Architecture overview
    ├── STYLE_GUIDE.md          # Coding standards
    ├── SECURITY.md             # Security guidelines
    └── TESTING_GUIDELINES.md   # Testing requirements
```

## 🎮 Monitoring Modes

### 1. **Integration Test Mode**
```bash
python test_integration.py
```
- ✅ Safe testing environment
- ✅ Parser validation with samples
- ✅ Live connection testing
- ⏰ Manual timeout control

### 2. **Basic Production Monitor**
```bash
python crypto_monitor.py
```
- 🚀 24/7 operation designed
- 📝 Enhanced logging to files
- 🛡️ Error recovery & retry logic
- 🔄 Graceful shutdown handling
- 📊 Real-time call counter
- 💾 SQLite storage only

### 3. **Enhanced Multi-Storage Monitor**
```bash
python crypto_monitor_enhanced.py
```
- 🚀 All basic monitor features
- 📊 Excel file export (.xlsx)
- 📋 Google Sheets integration
- 🔄 Multi-backend redundancy
- 📈 Enhanced storage status display
- 🛡️ Graceful degradation if backends fail

### 4. **Windows Service Mode**
```bash
start_monitor.bat
```
- 🖱️ Double-click to start
- ⚙️ Auto-activates virtual environment
- 📍 Shows all file locations
- 🛑 Easy manual stopping

## 🔗 Multi-Storage Setup

The enhanced monitor can save crypto calls to multiple destinations simultaneously:

### **SQLite Only** (Default)
```env
# Basic configuration - just Telegram credentials
API_ID=your_api_id
API_HASH=your_api_hash
```
```bash
python crypto_monitor.py  # or crypto_monitor_enhanced.py
```

### **SQLite + Excel Export**
```env
API_ID=your_api_id
API_HASH=your_api_hash
ENABLE_EXCEL=true
EXCEL_PATH=crypto_calls.xlsx
```
```bash
python crypto_monitor_enhanced.py
```

### **SQLite + Google Sheets**
```env
API_ID=your_api_id
API_HASH=your_api_hash
ENABLE_SHEETS=true
SHEET_ID=1a2b3c4d5e6f7g8h9i0j
GOOGLE_CREDENTIALS_PATH=credentials.json
```
```bash
python crypto_monitor_enhanced.py
```

### **All Three (SQLite + Excel + Google Sheets)**
```env
API_ID=your_api_id
API_HASH=your_api_hash
ENABLE_EXCEL=true
EXCEL_PATH=crypto_calls.xlsx
ENABLE_SHEETS=true
SHEET_ID=1a2b3c4d5e6f7g8h9i0j
GOOGLE_CREDENTIALS_PATH=credentials.json
```
```bash
python crypto_monitor_enhanced.py
```

### **Google Sheets Setup**

1. **Create Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create new project or select existing

2. **Enable Google Sheets API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Sheets API" and enable it

3. **Create Service Account**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service Account"
   - Download the JSON credentials file

4. **Setup Google Sheet**:
   - Create a new Google Sheet
   - Share it with the service account email (found in credentials.json)
   - Give "Editor" permissions
   - Copy the Sheet ID from the URL

5. **Configure Environment**:
   ```env
   GOOGLE_CREDENTIALS_PATH=path/to/your/credentials.json
   SHEET_ID=your_sheet_id_from_url
   ENABLE_SHEETS=true
   ```

### **Enhanced Monitor Features**

When running the enhanced monitor, you'll see:

```
🎧 ENHANCED CRYPTO CALL MONITOR - RUNNING
======================================================================
📢 Monitoring: @pfultimate
💾 Storage Backends: SQLite + Excel + Google Sheets
📝 Logs: logs/crypto_monitor_enhanced.log
🛑 Stop: Press Ctrl+C
======================================================================

🚀 CRYPTO CALL DETECTED #1
   Token: SOLANA
   Entry: $100,000
   Peak: $1,500,000
   Gain: 15x (VIP: 15x)
   Stored: SQLite + Excel + Sheets
   Time: 14:32:45
------------------------------------------------------------
```

**Key Benefits:**
- **Redundancy**: Data saved to multiple locations
- **Flexibility**: Excel for analysis, Sheets for collaboration
- **Reliability**: If one backend fails, others continue
- **Real-time**: See exactly where data is being stored

## 💾 Database & Analytics

### Database Files
- **Production**: `crypto_calls_production.db`
- **Testing**: `test_crypto_calls.db`

### Database Schema
```sql
CREATE TABLE crypto_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_name TEXT,           -- Token symbol (e.g., "SUNSET")
    entry_cap REAL,           -- Entry market cap
    peak_cap REAL,            -- Peak market cap  
    x_gain REAL,              -- Gain multiplier
    vip_x REAL,               -- VIP gain multiplier
    timestamp TEXT,           -- Message timestamp
    message_id INTEGER,       -- Telegram message ID
    channel_name TEXT,        -- Source channel
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Supported Message Formats

**@pfultimate Format (Primary):**
```
🎉 1.7x(3.8x from VIP) | 💹From 53.3K ↗️ 91.4K within 1m
```

**Traditional Format (Fallback):**
```
🚀 $TOKEN Entry: 45K MC Peak: 180K MC (4x)
⚡️ Entry 50k Peak 250k (5x VIP)
```

## 🔧 Troubleshooting

### Common Issues & Solutions

#### ❌ "ModuleNotFoundError: No module named 'pydantic'"
```bash
pip install pydantic pydantic-settings
```

#### ❌ "User not authorized"
```bash
python authenticate_telegram.py
```

#### ❌ "No crypto calls detected"
**Possible causes:**
- Messages don't match parser format
- Not subscribed to @pfultimate  
- Channel permissions restricted

**Debug steps:**
```bash
# Test parser with real message
python test_real_message.py

# Check if subscribed to channel
python find_channels.py

# View raw database info
python view_database.py  # Option 2
```

#### ❌ "Connection failed"
**Check:**
- Internet connection stable
- API credentials correct in `.env`
- Not hitting Telegram rate limits

#### ❌ Database locked/corrupted
```bash
# Backup current database
copy crypto_calls_production.db crypto_calls_backup.db

# The app will recreate the database on next run
```

### Debug Mode

Enable detailed logging by editing `crypto_monitor.py`:
```python
logging.basicConfig(level=logging.DEBUG)  # Change from INFO to DEBUG
```

## 🛠️ Maintenance

### Daily Checks
- ✅ Monitor is running (`python crypto_monitor.py` active)
- ✅ New calls being detected (check console output)
- ✅ Database growing (`python view_database.py`)

### Weekly Maintenance
```bash
# Check database size and performance
python view_database.py

# Review logs for errors
# Check: logs/crypto_monitor.log

# Backup database
copy crypto_calls_production.db backups/crypto_calls_YYYY-MM-DD.db
```

### Log Management
**Location**: `logs/crypto_monitor.log`

**Rotation**: Manual (implement logrotate if needed)

**Monitoring**: Check for ERROR entries
```bash
# Search for errors in logs (Windows)
findstr "ERROR" logs\crypto_monitor.log

# Linux/macOS
grep "ERROR" logs/crypto_monitor.log
```

### Database Backup
```bash
# Manual backup
copy crypto_calls_production.db backups/

# Automated backup (add to scheduler)
# Windows Task Scheduler or Linux cron
```

## ⚙️ Advanced Configuration

### Adding More Channels

Edit `crypto_monitor.py`:
```python
self.channels = [
    ChannelConfig(
        channel_id=-1002380293749,  # @pfultimate
        channel_name="Pumpfun Ultimate Alert",
        keywords=["🎉", "💹", "↗️", "x", "VIP"],
        priority="high"
    ),
    ChannelConfig(
        channel_id=-1001234567890,  # Additional channel
        channel_name="Another Channel", 
        keywords=["Entry", "Peak", "x"],
        priority="medium"
    )
]
```

### Custom Parser Patterns

Edit `src/parser.py` to add new message formats:
```python
# Add your custom pattern in parse_crypto_call()
custom_pattern = r"your_regex_pattern_here"
custom_match = re.search(custom_pattern, message)
```

### Export Options

**Excel Export** (future feature):
```python
from src.storage.excel import ExcelStorage
storage = ExcelStorage("crypto_calls.xlsx")
```

**Google Sheets** (future feature):
```python
from src.storage.sheet import GoogleSheetsStorage
storage = GoogleSheetsStorage(sheet_id)
```

### Running as Windows Service

For true 24/7 operation, consider:
1. **NSSM** (Non-Sucking Service Manager)
2. **Windows Task Scheduler** (startup trigger)
3. **PM2** for Node.js-style process management

## 🎯 Success Metrics

**Monitor is working correctly when:**
- ✅ Console shows "CRYPTO CALL DETECTED" messages
- ✅ Database record count increases (`python view_database.py`)
- ✅ Log file shows successful connections (`logs/crypto_monitor.log`)
- ✅ No error messages in logs
- ✅ Graceful shutdown preserves data

## 📞 Support

**Log Analysis**: Check `logs/crypto_monitor.log` for detailed error information

**Database Issues**: Use `python view_database.py` option 2 for raw debugging

**Parser Issues**: Test with `python test_real_message.py`

**Connection Issues**: Re-run `python authenticate_telegram.py`

---

## 🚀 Quick Commands Cheat Sheet

```bash
# Setup (one-time)
python authenticate_telegram.py

# Start monitoring
python crypto_monitor.py              # Basic (SQLite only)
python crypto_monitor_enhanced.py     # Enhanced (multi-storage)

# View data
python view_database.py

# Test parser
python test_integration.py

# Find channels
python find_channels.py

# Test real format
python test_real_message.py

# Configuration
copy env.example .env                  # Create configuration file
```

**🎉 You're ready to track crypto calls like a pro!** 