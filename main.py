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

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_enabled_countries():
    """Fetch enabled countries from Supabase"""
    try:
        response = supabase.table('countries_d257add4').select('*').eq('enabled', True).order('priority').execute()
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
            'country': country_code,
            'status': status,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        supabase.table('logs_d257add4').insert(log_entry).execute()
    except Exception as e:
        logger.error(f"Error logging scan: {e}")

async def scan_country(country_code: str, country_name: str):
    """Scan a single country for VFS appointments"""
    try:
        logger.info(f"[{country_code}] Starting scan for {country_name}...")
        
        # VFS website check (basic HTTP request)
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Example VFS URL - adjust based on actual VFS URLs
            url = f"https://visa.vfsglobal.com/{country_code.lower()}/en/check-appointment"
            
            try:
                response = await client.get(url)
                
                if response.status_code == 200:
                    # Basic check - look for "available" keyword
                    content = response.text.lower()
                    
                    if "available" in content or "book" in content:
                        logger.info(f"[{country_code}] ✅ POTENTIAL APPOINTMENTS FOUND!")
                        await log_scan(country_code, 'available', 'Potential appointments detected')
                        status = 'available'
                    else:
                        logger.info(f"[{country_code}] No appointments available")
                        await log_scan(country_code, 'unavailable', 'No appointments found')
                        status = 'unavailable'
                else:
                    logger.warning(f"[{country_code}] HTTP {response.status_code}")
                    await log_scan(country_code, 'error', f'HTTP {response.status_code}')
                    status = 'error'
                    
            except httpx.TimeoutException:
                logger.error(f"[{country_code}] Request timeout")
                await log_scan(country_code, 'error', 'Request timeout')
                status = 'error'
            except Exception as req_error:
                logger.error(f"[{country_code}] Request error: {req_error}")
                await log_scan(country_code, 'error', str(req_error))
                status = 'error'
        
        # Update last scan time in countries table
        supabase.table('countries_d257add4').update({
            'last_scan': datetime.utcnow().isoformat()
        }).eq('code', country_code).execute()
        
    except Exception as e:
        logger.error(f"[{country_code}] Error scanning: {e}")
        await log_scan(country_code, 'error', str(e))

async def main_loop():
    """Main worker loop"""
    logger.info("🚀 Starting VFS Scanner Worker...")
    logger.info(f"✅ Connected to Supabase: {SUPABASE_URL}")
    
    while True:
        try:
            # Get enabled countries
            countries = await get_enabled_countries()
            logger.info(f"📍 Scanning {len(countries)} enabled countries")
            
            # Scan each country
            for country in countries:
                country_code = country.get('code')
                country_name = country.get('name')
                if country_code:
                    await scan_country(country_code, country_name)
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
