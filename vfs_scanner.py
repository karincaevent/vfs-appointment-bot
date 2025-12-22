"""
VFS Global Appointment Scanner
Playwright-based scraper with stealth mode and country-specific configs
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Page, Browser
from playwright_stealth import stealth_async
from country_configs import get_country_config
from human_behavior import HumanBehavior


class VFSScanner:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        
    async def init_browser(self):
        """Initialize browser with stealth mode"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
            ]
        )
        
    async def close_browser(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
            
    async def scan_country(self, country_code: str, country_name: str) -> Dict:
        """
        Scan VFS Global for appointments in a specific country
        
        Returns:
            {
                'success': bool,
                'country': str,
                'has_appointment': bool,
                'available_slots': List[str] or None,
                'message': str,
                'scan_duration_ms': int
            }
        """
        start_time = datetime.now()
        
        try:
            # Get country-specific configuration
            config = get_country_config(country_code)
            url = config['appointment_url']
            
            print(f"🌍 Scanning {country_name} ({country_code})")
            print(f"📍 URL: {url}")
            
            # Create new page
            page = await self.browser.new_page()
            
            # Apply stealth mode
            await stealth_async(page)
            
            # 🎭 RANDOM USER-AGENT (Anti-bot detection)
            user_agent = HumanBehavior.get_random_user_agent()
            print(f"🎭 Using User-Agent: {user_agent[:50]}...")
            
            # Set viewport and user agent
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.set_extra_http_headers({
                'User-Agent': user_agent,  # 🔥 ROTATED USER-AGENT
                'Accept-Language': 'en-US,en;q=0.9,tr;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            })
            
            # Navigate with timeout
            try:
                print(f"🔄 Navigating to page...")
                await page.goto(url, wait_until='networkidle', timeout=config['timeout'])
                print(f"✅ Page loaded")
            except Exception as e:
                print(f"❌ Navigation failed: {str(e)}")
                await page.close()
                return {
                    'success': False,
                    'country': country_name,
                    'has_appointment': False,
                    'available_slots': None,
                    'message': f'Navigation failed: {str(e)[:100]}',
                    'scan_duration_ms': int((datetime.now() - start_time).total_seconds() * 1000)
                }
            
            # 👤 HUMAN BEHAVIOR SIMULATION
            # This is critical for avoiding bot detection!
            await HumanBehavior.simulate_full_page_interaction(page)
            
            # Wait for main content to load
            try:
                print(f"⏳ Waiting for appointment content...")
                await page.wait_for_selector(config['wait_for'], timeout=10000)
                print(f"✅ Content loaded")
            except Exception as e:
                print(f"⚠️  Timeout waiting for selector (continuing anyway)")
            
            # Check for appointment availability
            has_appointment = False
            available_slots = []
            message = "Unknown status"
            
            # 1. First check for "no appointment" messages
            print(f"🔍 Checking for 'no appointment' messages...")
            no_appt_found = False
            
            for selector in config['selectors']['no_appointment']:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        no_appt_found = True
                        print(f"   ✓ Found 'no appointment' message: {selector}")
                        break
                except Exception:
                    continue
            
            if no_appt_found:
                message = "No appointments available"
                print(f"❌ {message}")
            else:
                # 2. Check for available appointment slots
                print(f"🔍 Checking for available appointment slots...")
                
                for selector in config['selectors']['appointment_slots']:
                    try:
                        slots = await page.locator(selector).all()
                        if len(slots) > 0:
                            has_appointment = True
                            print(f"   ✓ Found {len(slots)} slots with: {selector}")
                            
                            # Extract dates from slots
                            for i, slot in enumerate(slots[:10]):  # Max 10 slots
                                try:
                                    date_text = await slot.inner_text()
                                    if date_text and date_text.strip():
                                        available_slots.append(date_text.strip())
                                except Exception:
                                    continue
                            
                            break
                    except Exception:
                        continue
                
                if has_appointment:
                    message = f"Found {len(available_slots)} available slots"
                    print(f"✅ {message}")
                    print(f"📅 Slots: {available_slots[:3]}...")
                else:
                    message = "No slots detected on page"
                    print(f"⚠️  {message}")
            
            # Take screenshot for debugging (optional)
            # await page.screenshot(path=f'/tmp/{country_code}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
            
            await page.close()
            
            scan_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            print(f"⏱️  Scan completed in {scan_duration}ms")
            
            return {
                'success': True,
                'country': country_name,
                'has_appointment': has_appointment,
                'available_slots': available_slots if has_appointment else None,
                'message': message,
                'scan_duration_ms': scan_duration
            }
            
        except Exception as e:
            scan_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            print(f"❌ Error scanning {country_name}: {str(e)}")
            
            return {
                'success': False,
                'country': country_name,
                'has_appointment': False,
                'available_slots': None,
                'message': f'Error: {str(e)[:100]}',
                'scan_duration_ms': scan_duration
            }


# Example usage
async def test_scanner():
    """Test the scanner"""
    scanner = VFSScanner(headless=True)
    await scanner.init_browser()
    
    result = await scanner.scan_country('germany', 'Germany')
    print(result)
    
    await scanner.close_browser()


if __name__ == "__main__":
    asyncio.run(test_scanner())
