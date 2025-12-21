"""
VFS Scanner Background Worker
Continuously scans VFS websites and updates Supabase
"""
import asyncio
import os
import logging
from datetime import datetime
from vfs_scanner import VFSScanner
from supabase import create_client, Client

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_enabled_countries():
    """Fetch enabled countries from Supabase"""
    try:
        response = supabase.rpc('kv_get', {'key_param': 'countries'}).execute()
        if response.data:
            countries = response.data
            return [c for c in countries if c.get('enabled', False)]
        return []
    except Exception as e:
        logger.error(f"Error fetching countries: {e}")
        return []

async def log_scan(country_code: str, status: str, message: str):
    """Log scan to Supabase"""
    try:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'country': country_code,
            'status': status,
            'message': message
        }
        supabase.rpc('kv_set', {
            'key_param': f'log_{country_code}_{datetime.utcnow().timestamp()}',
            'value_param': log_entry
        }).execute()
    except Exception as e:
        logger.error(f"Error logging scan: {e}")

async def scan_country(country_code: str, scanner: VFSScanner):
    """Scan a single country"""
    try:
        logger.info(f"[{country_code}] Starting scan...")
        
        result = await scanner.scan_appointments(country_code)
        
        if result.get('available'):
            logger.info(f"[{country_code}] ✅ APPOINTMENTS FOUND!")
            await log_scan(country_code, 'available', f"Found {len(result.get('appointments', []))} appointments")
        else:
            logger.info(f"[{country_code}] No appointments available")
            await log_scan(country_code, 'unavailable', 'No appointments found')
            
        # Update last scan time
        supabase.rpc('kv_set', {
            'key_param': f'last_scan_{country_code}',
            'value_param': {'timestamp': datetime.utcnow().isoformat()}
        }).execute()
        
    except Exception as e:
        logger.error(f"[{country_code}] Error scanning: {e}")
        await log_scan(country_code, 'error', str(e))

async def main_loop():
    """Main worker loop"""
    logger.info("🚀 Starting VFS Scanner Worker...")
    logger.info(f"✅ Connected to Supabase: {SUPABASE_URL}")
    
    scanner = VFSScanner()
    
    while True:
        try:
            # Get enabled countries
            countries = await get_enabled_countries()
            logger.info(f"📍 Scanning {len(countries)} enabled countries")
            
            # Scan each country
            for country in countries:
                country_code = country.get('code')
                if country_code:
                    await scan_country(country_code, scanner)
                    await asyncio.sleep(5)  # 5 seconds between countries
            
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
