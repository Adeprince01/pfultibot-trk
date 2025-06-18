#!/usr/bin/env python3
"""Comprehensive Message Collector for @pfultimate Analysis

This script collects ALL messages from @pfultimate with full metadata
to understand patterns and create better parsing/classification logic.

Stores everything in SQLite with rich metadata for analysis.
"""

import asyncio
import logging
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telethon import TelegramClient, events
from src.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/message_collection.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

class MessageCollector:
    """Comprehensive message collector and analyzer."""
    
    def __init__(self, db_path: str = "message_analysis.db"):
        """Initialize collector with database."""
        self.db_path = db_path
        self.message_count = 0
        self.session_start = datetime.now()
        self._init_database()
        
    def _init_database(self):
        """Initialize database with comprehensive schema."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                channel_id INTEGER,
                channel_name TEXT,
                message_text TEXT,
                message_date DATETIME,
                collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                -- Message characteristics
                char_length INTEGER,
                line_count INTEGER,
                word_count INTEGER,
                has_links BOOLEAN,
                has_emojis BOOLEAN,
                has_numbers BOOLEAN,
                has_parentheses BOOLEAN,
                has_brackets BOOLEAN,
                
                -- Crypto-specific flags
                has_cap_keyword BOOLEAN,
                has_entry_keyword BOOLEAN,
                has_peak_keyword BOOLEAN,
                has_from_keyword BOOLEAN,
                has_arrow_emoji BOOLEAN,
                has_celebration_emoji BOOLEAN,
                has_vip_keyword BOOLEAN,
                has_x_multiplier BOOLEAN,
                
                -- Classification attempts
                looks_like_discovery BOOLEAN,
                looks_like_update BOOLEAN,
                looks_like_result BOOLEAN,
                
                -- Parser results
                parser_success BOOLEAN,
                parsed_token_name TEXT,
                parsed_entry_cap REAL,
                parsed_peak_cap REAL,
                parsed_x_gain REAL,
                parsed_vip_x REAL
            )
        """)
        self.conn.commit()
        logger.info(f"Database initialized: {self.db_path}")
    
    def analyze_message_characteristics(self, text: str) -> dict:
        """Analyze message characteristics for pattern recognition."""
        if not text:
            text = ""
            
        characteristics = {
            'char_length': len(text),
            'line_count': text.count('\n') + 1,
            'word_count': len(text.split()),
            'has_links': 'http' in text.lower() or '[' in text,
            'has_emojis': any(ord(char) > 127 for char in text),
            'has_numbers': any(char.isdigit() for char in text),
            'has_parentheses': '(' in text or ')' in text,
            'has_brackets': '[' in text or ']' in text,
        }
        
        # Crypto-specific patterns
        text_lower = text.lower()
        characteristics.update({
            'has_cap_keyword': 'cap:' in text_lower,
            'has_entry_keyword': 'entry' in text_lower,
            'has_peak_keyword': 'peak' in text_lower,
            'has_from_keyword': 'from' in text_lower,
            'has_arrow_emoji': '↗️' in text,
            'has_celebration_emoji': '🎉' in text,
            'has_vip_keyword': 'vip' in text_lower,
            'has_x_multiplier': 'x' in text_lower and any(char.isdigit() for char in text),
        })
        
        # Message type classification
        characteristics.update({
            'looks_like_discovery': (
                characteristics['has_cap_keyword'] and 
                characteristics['has_brackets'] and
                characteristics['has_parentheses']
            ),
            'looks_like_update': (
                # Look for various update emojis + gain pattern + from/arrow
                any(emoji in text for emoji in ['🎉', '🔥', '🌕', '⚡️']) and
                (characteristics['has_from_keyword'] and characteristics['has_arrow_emoji']) or
                (characteristics['has_x_multiplier'] and 'within' in text_lower)
            ),
            'looks_like_result': (
                characteristics['has_entry_keyword'] and
                characteristics['has_peak_keyword'] and
                characteristics['has_x_multiplier']
            )
        })
        
        return characteristics
    
    def try_parse_message(self, text: str) -> dict:
        """Attempt to parse message and return results."""
        try:
            from src.parser import parse_crypto_call
            result = parse_crypto_call(text)
            
            if result:
                return {
                    'parser_success': True,
                    'parsed_token_name': result.get('token_name'),
                    'parsed_entry_cap': result.get('entry_cap'),
                    'parsed_peak_cap': result.get('peak_cap'),
                    'parsed_x_gain': result.get('x_gain'),
                    'parsed_vip_x': result.get('vip_x'),
                }
            else:
                return {'parser_success': False}
        except Exception as e:
            logger.debug(f"Parser failed: {e}")
            return {'parser_success': False}
    
    def store_message(self, message_id: int, channel_id: int, channel_name: str, 
                     text: str, message_date: datetime):
        """Store message with full analysis."""
        characteristics = self.analyze_message_characteristics(text)
        parser_results = self.try_parse_message(text)
        
        # Combine all data
        data = {
            'message_id': message_id,
            'channel_id': channel_id,
            'channel_name': channel_name,
            'message_text': text,
            'message_date': message_date.isoformat() if message_date else None,
            **characteristics,
            **parser_results
        }
        
        # Insert into database
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT OR REPLACE INTO messages ({columns}) VALUES ({placeholders})"
        
        self.conn.execute(query, list(data.values()))
        self.conn.commit()
        
        self.message_count += 1
        
        # Console output
        msg_type = "DISCOVERY" if characteristics['looks_like_discovery'] else \
                  "UPDATE" if characteristics['looks_like_update'] else \
                  "RESULT" if characteristics['looks_like_result'] else "OTHER"
        
        parse_status = "✅ PARSED" if parser_results.get('parser_success') else "❌ UNPARSED"
        
        print(f"\n📨 MESSAGE #{self.message_count} | {msg_type} | {parse_status}")
        print(f"Text: {text[:100]}{'...' if len(text) > 100 else ''}")
        if parser_results.get('parser_success'):
            token = parser_results.get('parsed_token_name', 'Unknown')
            gain = parser_results.get('parsed_x_gain', 0)
            print(f"Parsed: {token} | {gain}x gain")
        print("-" * 60)
    
    def print_stats(self):
        """Print collection statistics."""
        # Get stats from database
        cursor = self.conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(looks_like_discovery) as discoveries,
                SUM(looks_like_update) as updates,
                SUM(looks_like_result) as results,
                SUM(parser_success) as parsed_successfully
            FROM messages
        """)
        stats = cursor.fetchone()
        
        runtime = datetime.now() - self.session_start
        
        print(f"\n📊 COLLECTION STATISTICS")
        print(f"=" * 50)
        print(f"Runtime: {str(runtime).split('.')[0]}")
        print(f"Total Messages: {stats[0]}")
        print(f"Discovery Calls: {stats[1]}")
        print(f"Update Messages: {stats[2]}")
        print(f"Result Messages: {stats[3]}")
        print(f"Successfully Parsed: {stats[4]}")
        print(f"Parse Success Rate: {(stats[4]/max(stats[0], 1)*100):.1f}%")
        print(f"Database: {self.db_path}")
    
    def close(self):
        """Close database connection."""
        self.conn.close()

async def main():
    """Main collection function."""
    collector = MessageCollector()
    
    print("🔍 COMPREHENSIVE MESSAGE COLLECTION")
    print("=" * 60)
    print("Channel: @pfultimate")
    print("Goal: Collect ALL messages with full analysis")
    print("Database: message_analysis.db")
    print("Press Ctrl+C to stop and see statistics")
    print("=" * 60)
    
    # Create Telegram client
    client = TelegramClient(settings.tg_session, settings.api_id, settings.api_hash)
    
    try:
        # Connect
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Not authorized! Run authenticate_telegram.py first")
            return
        
        # Get channel info
        CHANNEL_ID = -1002380293749  # @pfultimate
        entity = await client.get_entity(CHANNEL_ID)
        print(f"✅ Connected to: {entity.title}")
        
        @client.on(events.NewMessage(chats=[CHANNEL_ID]))
        async def handler(event):
            message = event.message
            collector.store_message(
                message_id=message.id,
                channel_id=message.chat_id,
                channel_name=entity.title,
                text=message.text or "",
                message_date=message.date
            )
        
        print("🎧 Collection started...")
        await client.run_until_disconnected()
        
    except KeyboardInterrupt:
        print(f"\n🛑 Collection stopped by user")
        collector.print_stats()
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Collection error: {e}")
    finally:
        collector.close()
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 