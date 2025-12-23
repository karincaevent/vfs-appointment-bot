"""
VFS Global Appointment Scanner
Playwright-based scraper with stealth mode and country-specific configs
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import stealth_async
from country_configs import get_country_config
from human_behavior import HumanBehavior
from vfs_login import ensure_logged_in
from session_manager import save_session

class VFSScanner:
    def __init__(self, headless: bool = True, proxy: Optional[str] = None, proxy_config: Optional[Dict] = None):
        self.headless = headless
        self.proxy = proxy
        self.proxy_config = proxy_config  # 🔥 NEW: BrightData config (username, password)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
     async def init_browser(self):
        """Initialize browser with stealth mode and proxy support"""
        self.playwright = await async_playwright().start()
        
        # 🔥 NEW: Try BrightData Scraping Browser (CloudFlare bypass built-in!)
        if self.proxy_config:
            try:
                print("🌐 Attempting to connect to BrightData Scraping Browser...")
                
                # BrightData Scraping Browser WebSocket endpoint
                # Format: wss://USERNAME:PASSWORD@brd.superproxy.io:9222
                ws_endpoint = (
                    f"wss://{self.proxy_config['proxy_username']}:{self.proxy_config['proxy_password']}"
                    f"@brd.superproxy.io:9222"
                )
                
                print(f"   Endpoint: wss://***:***@brd.superproxy.io:9222")
                
                # Connect via Chrome DevTools Protocol
                self.browser = await self.playwright.chromium.connect_over_cdp(ws_endpoint)
                
                # Use default context (BrightData manages it)
                if len(self.browser.contexts) > 0:
                    self.context = self.browser.contexts[0]
                else:
                    self.context = await self.browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        locale='tr-TR',
                        timezone_id='Europe/Istanbul',
                    )
                
                print("✅ Connected to BrightData Scraping Browser (CloudFlare bypass enabled!)") 
                return  # Success! Skip normal browser launch
                
            except Exception as e:
                print(f"⚠️  BrightData Scraping Browser failed: {e}")
                print(f"   Falling back to normal proxy mode...")
        
        # Fallback: Normal browser launch with proxy
        # Browser launch options
        launch_options = {
            'headless': self.headless,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',  # 🔥 NEW: Disable web security for proxy
                '--disable-features=IsolateOrigins,site-per-process',  # 🔥 NEW: Better proxy compatibility
                '--disable-site-isolation-trials',  # 🔥 NEW
                '--window-size=1920,1080',  # 🔥 NEW: Set window size
            ],
            'chromium_sandbox': False,  # 🔥 NEW: Disable sandbox for Railway
        }
        
        # 🔥 ADD PROXY WITH AUTHENTICATION (BrightData)
        if self.proxy_config:
            # BrightData residential proxy with authentication
            proxy_server = f"http://{self.proxy_config.get('proxy_host', 'brd.superproxy.io')}:{self.proxy_config.get('proxy_port', 33335)}"
            launch_options['proxy'] = {
                'server': proxy_server,
                'username': self.proxy_config['proxy_username'],
                'password': self.proxy_config['proxy_password'],
            }
            print(f"🌐 Using BrightData Proxy: {proxy_server} (user: {self.proxy_config['proxy_username']})")
        elif self.proxy:
            # Legacy simple proxy (no auth)
            launch_options['proxy'] = {'server': self.proxy}
            print(f"🌐 Using proxy: {self.proxy}")
        
        self.browser = await self.playwright.chromium.launch(**launch_options)
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=HumanBehavior.get_random_user_agent(),
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
            ignore_https_errors=True,  # 🔥 NEW: Ignore SSL errors when using proxy
        )
        
    async def close_browser(self):
        """Close browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def scan_country(
        self, 
        country_code: str, 
        country_name: str,
        user_id: str = None,
        vfs_credentials: dict = None,
        email_credentials: dict = None,
        session_data: dict = None,
        vfs_session: dict = None,  # 🔥 NEW: Manual session from frontend (JWT + csk_str)
        proxy_config: dict = None,  # 🔥 NEW: BrightData proxy config
    ) -> Dict:
        """
        Scan VFS Global for appointments in a specific country
        
        Args:
            country_code: Country code (e.g., 'nld', 'deu')
            country_name: Country name
            user_id: User ID (for session management)
            vfs_credentials: VFS login credentials
            email_credentials: Email credentials for OTP
            session_data: Existing session data
            vfs_session: Manual session data (JWT, csk_str) for Cloudflare bypass
            proxy_config: BrightData proxy configuration
        
        Returns:
            {
                'success': bool,
                'country': str,
                'has_appointment': bool,
                'available_slots': List[str] or None,
                'message': str,
                'scan_duration_ms': int,
                'session_saved': bool,  # New: indicates if session was saved
            }
        """
        start_time = datetime.now()
        page = None
        session_saved = False
        
        try:
            # Get country-specific configuration
            config = get_country_config(country_code)
            
            print(f"🌍 Scanning {country_name} ({country_code})")
            
            # 🔥 PRIORITY 1: Check if manual session provided (Cloudflare bypass)
            # ❌ DISABLED: Session injection doesn't work - Cloudflare detects different IP/TLS fingerprint
            # Use auto-login instead (PRIORITY 2 below)
            if False and vfs_session and vfs_session.get('JWT') and vfs_session.get('csk_str'):
                print(f"🚀 Using MANUAL SESSION (Cloudflare bypass)")
                print(f"   JWT: {vfs_session.get('JWT')[:50]}...")
                print(f"   csk_str: {vfs_session.get('csk_str')[:50]}...")
                print(f"   Email: {vfs_session.get('logged_email', 'N/A')}")
                
                # Create new page
                page = await self.context.new_page()
                await stealth_async(page)
                
                # Navigate to VFS
                url = config['base_url']
                print(f"📍 Navigating to: {url}")
                
                try:
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
                        'scan_duration_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                        'session_saved': False,
                    }
                
                # 🔥 INJECT SESSION INTO sessionStorage
                print(f"💉 Injecting session data...")
                try:
                    # Use JSON.stringify to safely escape special characters
                    import json
                    jwt_value = json.dumps(vfs_session.get("JWT", ""))
                    csk_str_value = json.dumps(vfs_session.get("csk_str", ""))
                    email_value = json.dumps(vfs_session.get("logged_email", ""))
                    
                    await page.evaluate(f'''() => {{
                        sessionStorage.setItem('JWT', {jwt_value});
                        sessionStorage.setItem('csk_str', {csk_str_value});
                        if ({email_value}) {{
                            sessionStorage.setItem('logged_email', {email_value});
                        }}
                    }}''')
                    print(f"✅ Session injected successfully")
                except Exception as e:
                    print(f"❌ Session injection failed: {e}")
                    # Continue anyway - maybe login flow will work
                
                # Reload to apply session
                print(f"🔄 Reloading page...")
                await page.reload(wait_until='networkidle')
                await asyncio.sleep(2)
                
                # 🔥 NAVIGATE TO DASHBOARD (where the booking button lives!)
                dashboard_url = f"{config['base_url']}/dashboard"
                print(f"📍 Navigating to dashboard: {dashboard_url}")
                await page.goto(dashboard_url, wait_until='networkidle', timeout=config['timeout'])
                
                # 🔥 WAIT FOR JAVASCRIPT TO EXECUTE (Angular/React app needs time)
                print(f"⏳ Waiting for JavaScript to load...")
                await asyncio.sleep(5)  # Give extra time for SPA to hydrate
                
                # Wait for network to be idle again
                await page.wait_for_load_state('networkidle', timeout=config['timeout'])
                print(f"✅ JavaScript loaded")
                
                # 🔥 VERIFY SESSION AFTER RELOAD
                print(f"🔍 Verifying session after reload...")
                try:
                    # 🔥 FIRST: Check for Cloudflare challenge
                    cloudflare_check = await page.evaluate('''() => {
                        const html = document.documentElement.innerHTML;
                        const bodyText = document.body ? document.body.innerText : '';
                        
                        return {
                            has_cf_challenge: html.includes('cf-challenge') || html.includes('Just a moment') || html.includes('Checking your browser'),
                            has_cf_captcha: html.includes('cf-captcha') || bodyText.includes('Verify you are human'),
                            page_html_length: html.length,
                            body_text_length: bodyText.length
                        };
                    }''')
                    
                    print(f"   🛡️  Cloudflare Check:")
                    print(f"      Has Challenge: {cloudflare_check['has_cf_challenge']}")
                    print(f"      Has Captcha: {cloudflare_check['has_cf_captcha']}")
                    print(f"      HTML Length: {cloudflare_check['page_html_length']} bytes")
                    print(f"      Body Text Length: {cloudflare_check['body_text_length']} chars")
                    
                    if cloudflare_check['has_cf_challenge'] or cloudflare_check['has_cf_captcha']:
                        print(f"❌ CLOUDFLARE CHALLENGE DETECTED!")
                        print(f"   Session injection method FAILED - Cloudflare is blocking.")
                        raise Exception("Cloudflare challenge detected")
                    
                    if cloudflare_check['page_html_length'] < 1000:
                        print(f"⚠️  WARNING: Page HTML is suspiciously small ({cloudflare_check['page_html_length']} bytes)")
                        print(f"   This might indicate a loading error or challenge page.")
                    
                    session_check = await page.evaluate('''() => {
                        return {
                            has_jwt: !!sessionStorage.getItem('JWT'),
                            has_csk: !!sessionStorage.getItem('csk_str'),
                            has_email: !!sessionStorage.getItem('logged_email'),
                            current_url: window.location.href,
                            page_title: document.title,
                            body_text: document.body.innerText.substring(0, 500)
                        };
                    }''')
                    print(f"   JWT in sessionStorage: {session_check['has_jwt']}")
                    print(f"   csk_str in sessionStorage: {session_check['has_csk']}")
                    print(f"   Current URL: {session_check['current_url']}")
                    print(f"   Page Title: {session_check['page_title']}")
                    print(f"   Page Content Preview: {session_check['body_text'][:200]}")
                    
                    # 🔥 CHECK IF LOGGED IN
                    is_logged_in = await page.evaluate('''() => {
                        const bodyText = document.body.innerText.toLowerCase();
                        // Check for login indicators
                        const hasLoginButton = bodyText.includes('login') || bodyText.includes('sign in') || bodyText.includes('giriş');
                        const hasDashboard = bodyText.includes('dashboard') || bodyText.includes('panel') || bodyText.includes('rezervasyon');
                        const hasLogout = bodyText.includes('logout') || bodyText.includes('çıkış');
                        
                        return {
                            has_login_button: hasLoginButton,
                            has_dashboard: hasDashboard,
                            has_logout: hasLogout,
                            is_logged_in: (hasDashboard || hasLogout) && !hasLoginButton
                        };
                    }''')
                    
                    print(f"   Login Status Check:")
                    print(f"      Has Login Button: {is_logged_in['has_login_button']}")
                    print(f"      Has Dashboard: {is_logged_in['has_dashboard']}")
                    print(f"      Has Logout: {is_logged_in['has_logout']}")
                    print(f"      Is Logged In: {is_logged_in['is_logged_in']}")
                    
                    # Take screenshot for debugging
                    screenshot_path = f"/tmp/vfs_{country_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    await page.screenshot(path=screenshot_path)
                    print(f"   📸 Screenshot saved: {screenshot_path}")
                    
                    if not session_check['has_jwt']:
                        print(f"❌ SESSION LOST AFTER RELOAD! Falling back to login...")
                        raise Exception("Session lost after reload")
                    
                    if not is_logged_in['is_logged_in']:
                        print(f"⚠️  WARNING: Session exists but user appears NOT logged in!")
                        print(f"   This might be a Cloudflare challenge or expired session.")
                except Exception as e:
                    print(f"⚠️  Session verification failed: {e}")
                
                # Navigate to booking page
                print(f"📍 Navigating to appointment booking...")
                booking_clicked = False
                for selector in ['text="Yeni Rezervasyon Başlat"', 'text="New Reservation"', 'a[href*="new-booking"]']:
                    try:
                        if await page.locator(selector).count() > 0:
                            await page.click(selector)
                            booking_clicked = True
                            print(f"✅ Clicked: {selector}")
                            break
                    except:
                        continue
                
                if not booking_clicked:
                    print(f"⚠️  Trying direct appointment URL...")
                    await page.goto(f"{config['base_url']}/appointment", wait_until='networkidle', timeout=config['timeout'])
                
                await page.wait_for_load_state('networkidle')
                await HumanBehavior.simulate_full_page_interaction(page)
            
            # PRIORITY 2: If credentials provided, use login flow (FALLBACK)
            elif vfs_credentials and user_id:
                print(f"🔐 Using authenticated session")
                
                # Ensure logged in (restore session or fresh login)
                page, is_new_login = await ensure_logged_in(
                    context=self.context,
                    user_id=user_id,
                    vfs_credentials={
                        'email': vfs_credentials.get('vfs_email'),
                        'password': vfs_credentials.get('vfs_password'),  # Should be decrypted
                        'country_code': country_code,
                    },
                    email_credentials=email_credentials,
                    session_data=session_data,
                )
                
                # If new login, save session
                if is_new_login:
                    new_session = await save_session(self.context, user_id, country_code, expires_hours=24)
                    session_saved = True
                    print(f"💾 New session saved for {country_code.upper()}")
                
                # Navigate to appointment booking page
                # From dashboard, click "Yeni Rezervasyon Başlat"
                print(f"📍 Navigating to appointment booking...")
                
                new_booking_selectors = [
                    'text="Yeni Rezervasyon Başlat"',
                    'text="New Reservation"',
                    'a[href*="new-booking"]',
                    'button:has-text("Rezervasyon")',
                ]
                
                booking_clicked = False
                for selector in new_booking_selectors:
                    try:
                        if await page.locator(selector).count() > 0:
                            await page.click(selector)
                            booking_clicked = True
                            print(f"✅ Clicked: {selector}")
                            break
                    except:
                        continue
                
                if not booking_clicked:
                    print(f"⚠️  Could not find 'New Booking' button, trying direct URL")
                    # Try direct URL to appointment page (5th page)
                    appt_url = f"{config['base_url']}/application-detail"
                    await page.goto(appt_url, wait_until='networkidle', timeout=config['timeout'])
                
                # Wait for page load
                await page.wait_for_load_state('networkidle')
                
                # Human behavior simulation
                await HumanBehavior.simulate_full_page_interaction(page)
                
            else:
                # No credentials - try public page (may not work)
                print(f"⚠️  No credentials provided - attempting public access")
                url = config['appointment_url']
                print(f"📍 URL: {url}")
                
                # Create new page from context
                page = await self.context.new_page()
                
                # Apply stealth mode
                await stealth_async(page)
                
                # Navigate
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
                        'scan_duration_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                        'session_saved': False,
                    }
                
                # Human behavior simulation
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
            
            if page:
                await page.close()
            
            scan_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            print(f"⏱️  Scan completed in {scan_duration}ms")
            
            return {
                'success': True,
                'country': country_name,
                'has_appointment': has_appointment,
                'available_slots': available_slots if has_appointment else None,
                'message': message,
                'scan_duration_ms': scan_duration,
                'session_saved': session_saved,
            }
            
        except Exception as e:
            scan_duration = int((datetime.now() - start_time).total_seconds() * 1000)
            print(f"❌ Error scanning {country_name}: {str(e)}")
            
            if page:
                try:
                    await page.close()
                except:
                    pass
            
            return {
                'success': False,
                'country': country_name,
                'has_appointment': False,
                'available_slots': None,
                'message': f'Error: {str(e)[:100]}',
                'scan_duration_ms': scan_duration,
                'session_saved': False,
            }
