import csv
import re
from datetime import datetime

from telethon.sync import TelegramClient, events

# === STEP 1: Replace with your values ===
api_id = YOUR_API_ID  # e.g. 1234567
api_hash = "YOUR_API_HASH"  # e.g. 'abc123def456...'
session_name = "pumpfun_session"  # Can be any name, creates a .session file
channel_usernames = ["pfultimate"]  # Telegram usernames of the caller channels

# === STEP 2: Regex for extracting call data ===
call_regex = re.compile(
    r"(\d+(\.\d+)?x)\(.*?\) \|.*?From (\d+(\.\d+)?K) .*? (\d+(\.\d+)?K).*?within ([\dhms:]+)"
)

# === STEP 3: Output CSV ===
csv_file = "pumpfun_calls.csv"


# === Helper functions ===
def parse_k(k_string):
    return float(k_string.replace("K", "")) * 1000


def parse_multiplier(x_string):
    return float(x_string.replace("x", ""))


def parse_time(t_string):
    parts = t_string.split(":")
    parts = [int(p) for p in parts]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    elif len(parts) == 1:
        return parts[0]
    return 0


# === STEP 4: Create Telegram client ===
client = TelegramClient(session_name, api_id, api_hash)


@client.on(events.NewMessage(chats=channel_usernames))
async def handler(event):
    msg = event.raw_text
    match = call_regex.search(msg)
    if match:
        x = parse_multiplier(match.group(1))
        start = parse_k(match.group(3))
        end = parse_k(match.group(5))
        duration = match.group(7)
        secs = parse_time(duration)
        timestamp = datetime.now().isoformat()

        row = [timestamp, x, start, end, secs]

        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
        print(f"Logged: {row}")


# === STEP 5: Run client ===
with client:
    print("Listening for pumpfun calls...")
    client.run_until_disconnected()
