"""
VFS Scanner Background Worker
Continuously scans VFS websites and updates Supabase
"""
import asyncio
import os
import logging
from datetime import datetime
import httpx
from supabase import create_client, Client
import random

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
USE_MOCK_MODE = os.getenv("USE_MOCK_MODE", "true").lower() == "true"  # Default: mock mode

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Demo user ID (same as backend)
DEMO_USER_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'

async def get_enabled_countries():
    """Fetch enabled countries from Supabase"""
    try:
        response = supabase.table('countries_d257add4').select('*').eq('user_id', DEMO_USER_ID).eq('active', True).order('priority').execute()
        if response.data:
            return response.data
        return []
    except Exception as e:
        logger.error(f"Error fetching countries: {e}")
        return []

async def log_scan(country_code: str, status: str, message: str):
    """Log scan to Supabase"""
    try:
        log_entry = {
            'user_id': DEMO_USER_ID,
            'country_code': country_code,
            'status': status,
            'message': message,
            'created_at': datetime.utcnow().isoformat()
        }
        supabase.table('logs_d257add4').insert(log_entry).execute()
    except Exception as e:
        logger.error(f"Error logging scan: {e}")

async def check_cooldown(country_code: str, last_checked_at: str, cooldown_minutes: int):
    """Check if country is in cooldown period"""
    if not last_checked_at:
        return False, 0
    
    try:
        last_check = datetime.fromisoformat(last_checked_at.replace('Z', '+00:00'))
        now = datetime.utcnow().replace(tzinfo=last_check.tzinfo)
        elapsed = (now - last_check).total_seconds()
        cooldown_seconds = cooldown_minutes * 60
        
        if elapsed < cooldown_seconds:
            remaining = cooldown_seconds - elapsed
            return True, remaining
        
        return False, 0
    except Exception as e:
        logger.error(f"Error checking cooldown: {e}")
        return False, 0

async def mock_vfs_scan(country_code: str, country_name: str):
    """Mock VFS scan for testing (15% chance of finding appointment)"""
    await asyncio.sleep(random.uniform(0.5, 2.0))  # Simulate network delay
    
    # 15% chance of finding appointment
    has_appointment = random.random() < 0.15
    
    if has_appointment:
        # Generate random appointment slots
        num_slots = random.randint(1, 3)
        slots = []
        for _ in range(num_slots):
            day = random.randint(1, 30)
            hour = random.randint(9, 17)
            minute = random.choice([0, 30])
            slots.append(f"2025-01-{day:02d} {hour:02d}:{minute:02d}")
        
        return {
            'status': 'found',
            'message': f'Mock: Found {num_slots} appointments',
            'slots': slots
        }
    else:
        return {
            'status': 'no_appointment',
            'message': 'Mock: No appointments available',
            'slots': None
        }

async def real_vfs_scan(country_code: str, country_name: str):
    """Real VFS scan using HTTP request"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"https://visa.vfsglobal.com/{country_code.lower()}/en/check-appointment"
        
        try:
            response = await client.get(url, follow_redirects=True)
            
            if response.status_code == 200:
                content = response.text.lower()
                
                if "available" in content or "book" in content:
                    return {
                        'status': 'found',
                        'message': 'Potential appointments detected',
                        'slots': None
                    }
                else:
                    return {
                        'status': 'no_appointment',
                        'message': 'No appointments found',
                        'slots': None
                    }
            elif response.status_code == 403:
                return {
                    'status': 'error',
                    'message': 'HTTP 403 - Bot protection active (需要 Playwright)',
                    'slots': None
                }
            else:
                return {
                    'status': 'error',
                    'message': f'HTTP {response.status_code}',
                    'slots': None
                }
                
        except httpx.TimeoutException:
            return {
                'status': 'error',
                'message': 'Request timeout',
                'slots': None
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'slots': None
            }

async def scan_country(country_id: str, country_code: str, country_name: str, cooldown_minutes: int, last_checked_at: str):
    """Scan a single country for VFS appointments"""
    try:
        logger.info(f"[{country_code}] Starting scan for {country_name}...")
        
        # Check cooldown
        in_cooldown, remaining = await check_cooldown(country_code, last_checked_at, cooldown_minutes)
        
        if in_cooldown:
            remaining_min = int(remaining / 60)
            remaining_sec = int(remaining % 60)
            logger.info(f"[{country_code}] ⏳ Cooldown active: {remaining_min}m {remaining_sec}s remaining")
            await log_scan(country_code, 'error', f'Cooldown active ({remaining_min}m {remaining_sec}s remaining)')
            return
        
        # Perform scan (mock or real)
        if USE_MOCK_MODE:
            logger.info(f"[{country_code}] 🧪 Using MOCK mode")
            result = await mock_vfs_scan(country_code, country_name)
        else:
            logger.info(f"[{country_code}] 🌐 Using REAL mode")
            result = await real_vfs_scan(country_code, country_name)
        
        # Log result
        status = result['status']
        message = result['message']
        slots = result['slots']
        
        if status == 'found':
            logger.info(f"[{country_code}] ✅ APPOINTMENT FOUND! {message}")
            if slots:
                logger.info(f"[{country_code}] 📅 Slots: {', '.join(slots)}")
                message = f"{message} - Slots: {', '.join(slots)}"
        elif status == 'no_appointment':
            logger.info(f"[{country_code}] ❌ {message}")
        else:
            logger.warning(f"[{country_code}] ⚠️ {message}")
        
        # Save log
        await log_scan(country_code, status, message)
        
        # Update last_checked_at
        supabase.table('countries_d257add4').update({
            'last_checked_at': datetime.utcnow().isoformat()
        }).eq('id', country_id).execute()
        
        logger.info(f"[{country_code}] ✅ Scan completed")
        
    except Exception as e:
        logger.error(f"[{country_code}] ❌ Error scanning: {e}")
        await log_scan(country_code, 'error', str(e))

async def main_loop():
    """Main worker loop"""
    mode_text = "🧪 MOCK MODE" if USE_MOCK_MODE else "🌐 REAL MODE"
    logger.info(f"🚀 Starting VFS Scanner Worker ({mode_text})...")
    logger.info(f"✅ Connected to Supabase: {SUPABASE_URL}")
    
    while True:
        try:
            # Get enabled countries
            countries = await get_enabled_countries()
            logger.info(f"📍 Scanning {len(countries)} enabled countries")
            
            if len(countries) == 0:
                logger.info("⚠️ No active countries to scan")
            
            # Scan each country
            for country in countries:
                country_id = country.get('id')
                country_code = country.get('code')
                country_name = country.get('name')
                cooldown_minutes = country.get('cooldown_minutes', 5)
                last_checked_at = country.get('last_checked_at')
                
                if country_code and country_id:
                    await scan_country(country_id, country_code, country_name, cooldown_minutes, last_checked_at)
                    await asyncio.sleep(3)  # 3 seconds between countries
            
            # Wait 30 seconds before next full scan
            logger.info("⏸️  Waiting 30 seconds before next scan...")
            await asyncio.sleep(30)
            
        except KeyboardInterrupt:
            logger.info("👋 Shutting down worker...")
            break
        except Exception as e:
            logger.error(f"❌ Error in main loop: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main_loop())
