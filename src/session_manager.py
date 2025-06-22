"""Session file management for Telegram authentication.

This module handles session file creation from environment variables
for cloud deployments where persistent storage isn't available.
"""

import base64
import logging
import os
from pathlib import Path
from typing import Optional


def ensure_session_file(session_name: str = "pf_session") -> Optional[Path]:
    """Ensure Telegram session file exists, creating from env var if needed.
    
    This function checks if a session file exists locally. If not, it attempts
    to create one from the TG_SESSION_B64 environment variable. This is useful
    for cloud deployments where the session file can't be stored persistently.
    
    Args:
        session_name: Base name for the session file (without .session extension)
        
    Returns:
        Path to the session file if successful, None otherwise
        
    Raises:
        ValueError: If session data is invalid or corrupted
    """
    logger = logging.getLogger(__name__)
    
    # Define paths
    data_dir = Path("data")
    session_path = data_dir / f"{session_name}.session"
    
    # If session file already exists, return it
    if session_path.exists():
        logger.info(f"✅ Session file found: {session_path}")
        return session_path
    
    # Try to create from environment variable
    session_b64 = os.getenv("TG_SESSION_B64")
    if not session_b64:
        logger.warning("❌ No session file found and TG_SESSION_B64 not set")
        return None
    
    try:
        # Create data directory if needed
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Decode and write session file
        logger.info(f"📝 Creating session file from environment variable...")
        session_data = base64.b64decode(session_b64)
        session_path.write_bytes(session_data)
        
        logger.info(f"✅ Session file created: {session_path}")
        return session_path
        
    except Exception as e:
        logger.error(f"❌ Failed to create session file: {e}")
        raise ValueError(f"Invalid session data in TG_SESSION_B64: {e}")


def get_session_path(session_name: str = "pf_session") -> str:
    """Get the session file path, ensuring it exists.
    
    Args:
        session_name: Base name for the session file
        
    Returns:
        String path to the session file
        
    Raises:
        FileNotFoundError: If session file cannot be created or found
    """
    session_path = ensure_session_file(session_name)
    if not session_path:
        raise FileNotFoundError(
            "Session file not found and cannot be created from environment. "
            "Please ensure TG_SESSION_B64 environment variable is set or "
            "run authenticate_telegram.py to create a local session file."
        )
    return str(session_path) 