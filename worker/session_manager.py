"""
Session Manager
Saves and loads browser state (cookies, localStorage, sessionStorage)
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

# Session storage directory
SESSION_DIR = Path("/tmp/vfs_sessions")
SESSION_DIR.mkdir(exist_ok=True)


def get_session_path(user_id: str, country_code: str = None) -> Path:
    """Get session file path for user and country"""
    if country_code:
        return SESSION_DIR / f"session_{user_id}_{country_code}.json"
    return SESSION_DIR / f"session_{user_id}.json"


async def save_session(
    context: BrowserContext, 
    user_id: str, 
    country_code: str,
    expires_hours: int = 24
) -> dict:
    """
    Save browser context state (cookies, localStorage, sessionStorage)
    
    Args:
        context: Playwright browser context
        user_id: User ID
        country_code: Country code (e.g., 'nld', 'deu')
        expires_hours: Session expiration time in hours
        
    Returns:
        Session state dict with expiry timestamp
    """
    try:
        session_path = get_session_path(user_id, country_code)
        
        # Save storage state to file
        await context.storage_state(path=str(session_path))
        
        # Read the saved state
        with open(session_path, 'r') as f:
            state = json.load(f)
        
        # Add expiry timestamp
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        
        session_data = {
            'state': state,
            'expires_at': expires_at.isoformat(),
            'saved_at': datetime.utcnow().isoformat(),
        }
        
        logger.info(f"✅ Session saved for user {user_id} - {country_code.upper()} (expires: {expires_at})")
        
        return session_data
        
    except Exception as e:
        logger.error(f"❌ Error saving session: {e}")
        return None


async def load_session(context: BrowserContext, session_data: dict) -> bool:
    """
    Load session state into browser context
    
    Args:
        context: Playwright browser context
        session_data: Session data dict (from save_session)
        
    Returns:
        True if loaded successfully, False otherwise
    """
    try:
        if not session_data or 'state' not in session_data:
            logger.warning("⚠️  No session data to load")
            return False
        
        # Check if expired
        expires_at = datetime.fromisoformat(session_data['expires_at'])
        if datetime.utcnow() > expires_at:
            logger.warning("⚠️  Session expired")
            return False
        
        # Write state to temp file
        temp_path = SESSION_DIR / f"temp_{datetime.utcnow().timestamp()}.json"
        with open(temp_path, 'w') as f:
            json.dump(session_data['state'], f)
        
        # Load state into context
        await context.add_cookies(session_data['state'].get('cookies', []))
        
        # Clean up temp file
        temp_path.unlink()
        
        logger.info("✅ Session loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading session: {e}")
        return False


def is_session_valid(session_data: dict) -> bool:
    """
    Check if session is still valid
    
    Args:
        session_data: Session data dict
        
    Returns:
        True if valid, False otherwise
    """
    if not session_data or 'expires_at' not in session_data:
        return False
    
    try:
        expires_at = datetime.fromisoformat(session_data['expires_at'])
        # Add 5-minute buffer
        buffer_time = datetime.utcnow() + timedelta(minutes=5)
        return expires_at > buffer_time
    except:
        return False
