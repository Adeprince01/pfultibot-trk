#!/usr/bin/env python3
"""Crypto Call Monitor - Production Ready Tracker

Main production monitor for tracking crypto calls from Telegram channels.
Features:
- Multi-storage backends (SQLite + Excel + Google Sheets)
- Graceful degradation when backends fail
- Connection reliability and auto-reconnection
- Health monitoring and statistics
- Production-ready error handling
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.listener import ChannelConfig, MessageHandler, TelegramListener
from src.settings import settings
from src.storage.multi import MultiStorage

# Configure detailed logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "crypto_monitor_enhanced.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Fix Windows console encoding for emojis
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logger = logging.getLogger(__name__)


class EnhancedProductionStorage:
    """Enhanced production storage with multi-backend support and reliability features."""
    
    def __init__(self, db_path: Path) -> None:
        """Initialize enhanced production storage with multi-backend support."""
        self.db_path = db_path
        self.call_count = 0
        self.success_count = 0
        self.failure_count = 0
        
        # Initialize multi-storage based on settings
        self._init_multi_storage()
        
        logger.info(f"Enhanced storage initialized with backends: {', '.join(self.storage.active_backends)}")
    
    def _init_multi_storage(self) -> None:
        """Initialize multi-storage based on environment configuration."""
        excel_path = None
        if settings.enable_excel and settings.excel_path:
            excel_path = Path(settings.excel_path)
        
        credentials_path = None
        if settings.enable_sheets and settings.credentials_path:
            credentials_path = Path(settings.credentials_path)
        
        self.storage = MultiStorage(
            sqlite_path=self.db_path,
            excel_path=excel_path,
            sheet_id=settings.sheet_id if settings.enable_sheets else None,
            credentials_path=credentials_path
        )
    
    def append_row(self, data: Dict[str, any]) -> None:
        """Store crypto call with enhanced logging and error tracking."""
        try:
            self.storage.append_row(data)
            self.call_count += 1
            self.success_count += 1
            
            # Enhanced logging with backend status
            token = data.get('token_name', 'Unknown')
            gain = data.get('x_gain', 0)
            entry = data.get('entry_cap', 0)
            peak = data.get('peak_cap', 0)
            vip = f" (VIP: {data.get('vip_x')}x)" if data.get('vip_x') else ""
            
            backend_status = self.storage.get_backend_status()
            active_backends = [name.title() for name, active in backend_status.items() if active]
            
            logger.info(f"📈 CALL #{self.call_count}: {token} - {gain}x gain "
                       f"(${entry:,.0f} → ${peak:,.0f}){vip} "
                       f"[Stored: {' + '.join(active_backends)}]")
            
            # Enhanced console output
            print(f"\n🚀 CRYPTO CALL DETECTED #{self.call_count}")
            print(f"   Token: {token}")
            print(f"   Entry: ${entry:,.0f}")
            print(f"   Peak: ${peak:,.0f}")
            print(f"   Gain: {gain}x{vip}")
            print(f"   Stored: {' + '.join(active_backends)}")
            print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
            print("-" * 60)
            
        except Exception as e:
            self.failure_count += 1
            logger.error(f"Failed to store crypto call: {e}")
            print(f"❌ STORAGE ERROR: {e}")
    
    def get_records(self, limit: int = None) -> List[Dict[str, any]]:
        """Get stored records."""
        return self.storage.get_records(limit)
    
    def get_storage_stats(self) -> Dict[str, any]:
        """Get storage statistics and backend status."""
        backend_status = self.storage.get_backend_status()
        return {
            "total_calls": self.call_count,
            "successful_stores": self.success_count,
            "failed_stores": self.failure_count,
            "success_rate": (self.success_count / max(self.call_count, 1)) * 100,
            "active_backends": [name.title() for name, active in backend_status.items() if active],
            "backend_status": backend_status
        }
    
    def close(self) -> None:
        """Close storage with enhanced statistics."""
        stats = self.get_storage_stats()
        logger.info(f"Closing enhanced storage. Total calls: {stats['total_calls']}, "
                   f"Success rate: {stats['success_rate']:.1f}%")
        self.storage.close()


class EnhancedCryptoMonitor:
    """Enhanced crypto call monitor with reliability features."""
    
    def __init__(self) -> None:
        """Initialize the enhanced monitor."""
        self.storage = EnhancedProductionStorage(Path("crypto_calls_production.db"))
        self.listener = TelegramListener(settings)
        self.running = False
        self.start_time = None
        
        # Enhanced channel configuration with reliability features
        self.channels = [
            ChannelConfig(
                channel_id=-1002380293749,  # @pfultimate
                channel_name="Pumpfun Ultimate Alert", 
                keywords=["🎉", "💹", "↗️", "x", "VIP"],
                priority="high",
                retry_count=5,
                timeout=60
            )
        ]
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Enhanced CryptoMonitor initialized")
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    async def start_monitoring(self) -> None:
        """Start enhanced monitoring with reliability features."""
        logger.info("🚀 Starting enhanced crypto call monitoring...")
        self.start_time = datetime.now()
        
        try:
            # Connect to Telegram with retry logic
            logger.info("Connecting to Telegram...")
            connected = await self._connect_with_retry()
            
            if not connected:
                logger.error("Failed to connect to Telegram after retries")
                return
            
            logger.info("✅ Successfully connected to Telegram")
            
            # Setup message handler with enhanced configuration
            self.listener.setup_message_handler(self.channels, self.storage)
            
            # Start listening with reliability monitoring
            await self.listener.start_listening()
            self.running = True
            
            logger.info("🎧 Enhanced monitoring started - listening for crypto calls...")
            self._print_startup_banner()
            
            # Enhanced monitoring loop with health checks
            await self._monitoring_loop()
            
        except Exception as e:
            logger.error(f"Enhanced monitor error: {e}")
            
        finally:
            await self.shutdown()
    
    async def _connect_with_retry(self, max_retries: int = 3) -> bool:
        """Connect to Telegram with retry logic."""
        for attempt in range(max_retries):
            try:
                connected = await self.listener.connect()
                if connected:
                    return True
                
                logger.warning(f"Connection attempt {attempt + 1} failed, retrying...")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return False
    
    def _print_startup_banner(self) -> None:
        """Print enhanced startup banner with backend information."""
        stats = self.storage.get_storage_stats()
        active_backends = " + ".join(stats['active_backends'])
        
        print("\n" + "="*70)
        print("🎧 ENHANCED CRYPTO CALL MONITOR - RUNNING")
        print("="*70)
        print("📢 Monitoring: @pfultimate")
        print(f"💾 Storage Backends: {active_backends}")
        print("📝 Logs: logs/crypto_monitor_enhanced.log")
        print("🛑 Stop: Press Ctrl+C")
        print("="*70)
    
    async def _monitoring_loop(self) -> None:
        """Enhanced monitoring loop with health checks."""
        health_check_interval = 300  # 5 minutes
        last_health_check = datetime.now()
        
        while self.running:
            try:
                await asyncio.sleep(1)
                
                # Periodic health check
                now = datetime.now()
                if (now - last_health_check).seconds >= health_check_interval:
                    await self._health_check()
                    last_health_check = now
                    
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
    
    async def _health_check(self) -> None:
        """Perform periodic health check."""
        try:
            # Check Telegram connection
            if not self.listener.is_connected:
                logger.warning("Telegram connection lost, attempting reconnection...")
                await self._connect_with_retry()
            
            # Log storage statistics
            stats = self.storage.get_storage_stats()
            uptime = datetime.now() - self.start_time
            uptime_str = str(uptime).split('.')[0]  # Remove microseconds
            
            logger.info(f"Health Check - Uptime: {uptime_str}, "
                       f"Calls: {stats['total_calls']}, "
                       f"Success Rate: {stats['success_rate']:.1f}%")
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
    
    async def shutdown(self) -> None:
        """Enhanced graceful shutdown with statistics."""
        logger.info("🛑 Shutting down enhanced crypto monitor...")
        
        try:
            await self.listener.stop_listening()
            await self.listener.disconnect()
            
            # Get final statistics
            stats = self.storage.get_storage_stats()
            uptime = datetime.now() - self.start_time if self.start_time else "Unknown"
            
            self.storage.close()
            
            print("\n" + "="*70)
            print("✅ ENHANCED CRYPTO MONITOR STOPPED")
            print(f"📊 Total calls processed: {stats['total_calls']}")
            print(f"📈 Success rate: {stats['success_rate']:.1f}%")
            print(f"⏱️ Uptime: {str(uptime).split('.')[0] if self.start_time else 'Unknown'}")
            print(f"💾 Storage backends: {' + '.join(stats['active_backends'])}")
            print("📝 Logs saved to: logs/crypto_monitor_enhanced.log")
            print("="*70)
            
        except Exception as e:
            logger.error(f"Error during enhanced shutdown: {e}")
        
        logger.info("Enhanced crypto monitor shutdown complete")


async def main() -> None:
    """Main function."""
    print("🤖 Crypto Call Monitor - Production Ready")
    print("Multi-backend storage with graceful degradation")
    print()
    
    # Display configuration
    backends = []
    backends.append("SQLite")
    if settings.enable_excel:
        backends.append("Excel")
    if settings.enable_sheets:
        backends.append("Google Sheets")
    
    print(f"📊 Storage backends: {' + '.join(backends)}")
    print("💡 Monitor continues working even if some backends fail")
    print()
    
    try:
        monitor = EnhancedCryptoMonitor()
        await monitor.start_monitoring()
        
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 