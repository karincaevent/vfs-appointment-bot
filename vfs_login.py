"""
VFS Login Flow
Handles login to VFS Global appointment system
"""

import asyncio
import random
import logging
from playwright.async_api import Page, Browser, BrowserContext
from playwright_stealth import stealth_async
from email_otp_reader import read_otp_from_email
from session_manager import save_session, load_session, is_session_valid

logger = logging.getLogger(__name__)


async def human_like_delay(min_ms: int = 500, max_ms: int = 2000):
    """Random delay to simulate human behavior"""
    delay = random.uniform(min_ms / 1000, max_ms / 1000)
    await asyncio.sleep(delay)


async def human_like_typing(page: Page, selector: str, text: str):
    """Type text with human-like delays between keystrokes"""
    await page.fill(selector, '')  # Clear first
    await human_like_delay(200, 500)
    
    for char in text:
        await page.type(selector, char, delay=random.uniform(50, 150))
        await asyncio.sleep(random.uniform(0.01, 0.05))


async def click_with_human_behavior(page: Page, selector: str):
    """Click element with human-like behavior"""
    # Random mouse movement before click
    await page.mouse.move(
        random.uniform(100, 500),
        random.uniform(100, 500)
    )
    await human_like_delay(100, 300)
    
    # Click
    await page.click(selector)
    await human_like_delay(500, 1500)


async def wait_for_otp_manual(timeout_seconds: int = 120) -> str:
    """
    Wait for user to manually enter OTP (fallback)
    For demo purposes - in production, use email auto-reading
    """
    print(f"⏳ Manual OTP input required (timeout: {timeout_seconds}s)")
    print("   VFS will send OTP to registered email")
    print("   This is a fallback - configure email credentials for auto OTP")
    
    # In production, this would be a webhook/API call
    # For now, return empty string to indicate manual intervention needed
    return ""


async def login_to_vfs(
    page: Page,
    email: str,
    password: str,
    country_code: str,
    email_credentials: dict = None,
) -> dict:
    """
    Login to VFS Global appointment system
    
    Flow:
    1. Go DIRECTLY to login page (skip homepage!)
    2. Enter email and password
    3. Read OTP from email (or wait for manual input)
    4. Enter OTP and verify
    5. Navigate to dashboard
    
    Args:
        page: Playwright page
        email: VFS account email
        password: VFS account password
        country_code: Country code (e.g., 'nld', 'deu')
        email_credentials: Optional email credentials for OTP auto-reading
        
    Returns:
        {
            'success': bool,
            'message': str,
            'otp_method': 'auto' | 'manual' | 'failed'
        }
    """
    try:
        # ✅ CRITICAL FIX: Set longer timeouts to prevent browser/page from closing!
        print("⚙️  Setting extended timeouts (2 minutes) to prevent premature closure...")
        page.set_default_timeout(120000)  # 2 dakika
        page.set_default_navigation_timeout(120000)  # 2 dakika
        
        # Go DIRECTLY to login page, not homepage!
        login_url = f"https://visa.vfsglobal.com/tur/tr/{country_code.lower()}/login"
        
        print(f"🌍 Navigating DIRECTLY to login page: {login_url}")
        print("   Skipping homepage to avoid button detection issues")
        
   # Apply stealth
        await stealth_async(page)

        # 🔍 NETWORK LOGGING - Hangi dosyalar yükleniyor/engelleniyor?
        print("\n🔍 ========== NETWORK LOGGING ENABLED ==========")

        # Giden istekleri takip et
        def log_request(request):
            url_short = request.url[:120] if len(request.url) > 120 else request.url
            print(f"🚀 >> {request.method:6s} | {request.resource_type:10s} | {url_short}")

        page.on("request", log_request)

        # Gelen cevapları takip et (Status code'ları yakala!)
        def log_response(response):
            url_short = response.url[:120] if len(response.url) > 120 else response.url
            status_emoji = "✅" if response.ok else "❌"
            print(f"{status_emoji} << {response.status:3d} | {response.url[:120]}")

        page.on("response", log_response)

        # Başarısız olan (Bloklanan) istekleri yakala
        def log_failed_request(request):
            url_short = request.url[:120] if len(request.url) > 120 else request.url
            failure = request.failure
            error_text = failure if failure else "Unknown error"
            print(f"🔴 !! FAILED: {url_short}")
            print(f"   └─ Error: {error_text}")

        page.on("requestfailed", log_failed_request)

        print("🔍 ===============================================\n")
        
        # 🔥 NEW: Additional anti-detection (WebDriver, Chrome object, etc.)
        await page.add_init_script("""
            // Hide WebDriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Add Chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Plugin array
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['tr-TR', 'tr', 'en-US', 'en']
            });
        """)
        
        # 1. Go to login page
        try:
            await page.goto(login_url, wait_until='domcontentloaded', timeout=60000)
            print("✅ Login page loaded")
        except Exception as e:
            print(f"❌ Could not load login page: {e}")
            return {
                'success': False,
                'message': f'Login page load failed: {str(e)}',
                'otp_method': 'failed',
                'debug': {'stage': 'page_load', 'url': login_url}
            }
        
        # 🔥 NEW: Wait for CloudFlare challenge to resolve (if present)
        print("⏳ Waiting for CloudFlare challenge (if any)...")
        await human_like_delay(3000, 5000)  # Initial wait
        
        # Check if CloudFlare challenge is present
        try:
            cloudflare_detected = await page.evaluate("""
                () => {
                    const title = document.title.toLowerCase();
                    const body = document.body.innerHTML.toLowerCase();
                    return title.includes('just a moment') || 
                           body.includes('checking your browser') ||
                           body.includes('cf-challenge');
                }
            """)
            
            if cloudflare_detected:
                print("⚠️  CloudFlare challenge detected, waiting up to 15s...")
                await asyncio.sleep(15)  # Give CloudFlare time to resolve
                
                # Check again
                cloudflare_still_there = await page.evaluate("""
                    () => {
                        const title = document.title.toLowerCase();
                        return title.includes('just a moment');
                    }
                """)
                
                if cloudflare_still_there:
                    print("❌ CloudFlare challenge still blocking after 15s!")
                    print("   This may indicate the proxy is flagged.")
                    await page.screenshot(path='/tmp/cloudflare_block.png')
                    return {
                        'success': False,
                        'message': 'CloudFlare challenge failed',
                        'otp_method': 'failed',
                        'debug': {'stage': 'cloudflare_challenge'}
                    }
                else:
                    print("✅ CloudFlare challenge passed!")
        except Exception as e:
            # ✅ CRITICAL FIX: Check if page closed during CloudFlare check!
            if 'closed' in str(e).lower() or 'target' in str(e).lower():
                print(f"🔴 CRITICAL: Page closed during CloudFlare check!")
                return {
                    'success': False,
                    'message': f'Page closed during CloudFlare check: {str(e)}',
                    'otp_method': 'failed',
                    'debug': {'stage': 'cloudflare_check_error'}
                }
            else:
                print(f"⚠️  Could not check CloudFlare status: {e}")
        
        # Wait for page to settle
        await human_like_delay(2000, 4000)
        
        print("📍 Step 1/6: Login page ready")
        
        # DEBUG: Take early screenshot and check page state
        try:
            page_html = await page.content()
            page_title = await page.title()
            page_url = page.url
            
            print(f"📄 [EARLY CHECK] Page HTML length: {len(page_html)} characters")
            print(f"📄 [EARLY CHECK] Page title: {page_title}")
            print(f"📄 [EARLY CHECK] Page HTML preview (first 1000 chars):")
            print(page_html[:1000])
            print(f"📄 [EARLY CHECK] Current URL: {page_url}")
            
            # Take early screenshot
            early_screenshot_path = '/tmp/vfs_login_early.png'
            await page.screenshot(path=early_screenshot_path)
            print(f"📸 [EARLY CHECK] Screenshot saved: {early_screenshot_path}")
            
        except Exception as e:
            print(f"⚠️  [EARLY CHECK] Could not get page info: {e}")
        
        # 🔥 NEW: Wait for Angular/React app to hydrate (JavaScript execution)
        print("⏳ Waiting for JavaScript to hydrate DOM (Angular/React SPA)...")
        
        # ✅ CRITICAL FIX: Check if page is still alive BEFORE waiting
        try:
            await page.evaluate("() => 1")  # Simple alive check
            print("✅ Page is alive and responsive")
        except Exception as e:
            print(f"🔴 CRITICAL: Page already closed before selector wait!")
            print(f"   Error: {e}")
            return {
                'success': False,
                'message': f'Page closed unexpectedly before JavaScript wait: {str(e)}',
                'otp_method': 'failed',
                'debug': {'stage': 'pre_selector_wait'}
            }
        
        # Try to wait for email input with multiple selectors
        email_input_ready = False
        email_selectors_to_try = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id="email"]',
            '#mat-input-0',  # Angular Material
        ]
        
        for selector in email_selectors_to_try:
            try:
                print(f"   🔍 Trying to wait for: {selector}")
                await page.wait_for_selector(selector, timeout=20000, state='visible')
                print(f"   ✅ Found email input: {selector}")
                email_input_ready = True
                break
            except TimeoutError:
                print(f"   ⏭️  Selector {selector} timeout, trying next...")
                continue
            except Exception as e:
                # ✅ CRITICAL FIX: Check if browser/page closed!
                if 'closed' in str(e).lower() or 'target' in str(e).lower():
                    print(f"   🔴 CRITICAL: Browser/Page closed while waiting for {selector}!")
                    print(f"      Error: {e}")
                    return {
                        'success': False,
                        'message': f'Browser/Page closed during selector wait: {str(e)}',
                        'otp_method': 'failed',
                        'debug': {'stage': 'selector_wait', 'selector': selector}
                    }
                else:
                    print(f"   ⚠️  Selector {selector} error: {e}, trying next...")
                    continue
        
        # ✅ CRITICAL FIX: Improved JavaScript wait with page alive checks
        if not email_input_ready:
            print("   ⚠️  No email input found via wait_for_selector, trying longer wait...")
            print("   🔄 Waiting up to 30 seconds for JavaScript to execute...")
            
            for attempt in range(6):  # 6 attempts x 5 seconds = 30 seconds
                # ✅ CRITICAL FIX: Check if page is still alive FIRST!
                try:
                    await page.evaluate("() => 1")  # Simple alive check
                    print(f"   ✅ [Attempt {attempt + 1}/6] Page is still alive")
                except Exception as e:
                    print(f"   🔴 CRITICAL: Page closed at attempt {attempt + 1}!")
                    print(f"      Error: {e}")
                    return {
                        'success': False,
                        'message': f'Browser/Page closed during JavaScript wait (attempt {attempt + 1}): {str(e)}',
                        'otp_method': 'failed',
                        'debug': {
                            'stage': 'javascript_wait',
                            'attempt': attempt + 1,
                            'waited_seconds': attempt * 5
                        }
                    }
                
                # Wait 5 seconds
                await asyncio.sleep(5)
                
                # Check if email input appeared
                try:
                    input_check = await page.evaluate("""
                        () => {
                            const inputs = document.querySelectorAll('input[type="email"], input[name="email"]');
                            return inputs.length > 0;
                        }
                    """)
                    
                    if input_check:
                        print(f"   ✅ Email input appeared after {(attempt + 1) * 5} seconds!")
                        email_input_ready = True
                        break
                    else:
                        print(f"   ⏳ Attempt {attempt + 1}/6: Still no email input...")
                except Exception as e:
                    # Check if page closed
                    if 'closed' in str(e).lower() or 'target' in str(e).lower():
                        print(f"   🔴 Page closed during evaluation at attempt {attempt + 1}!")
                        return {
                            'success': False,
                            'message': f'Page closed during JavaScript evaluation: {str(e)}',
                            'otp_method': 'failed',
                            'debug': {'stage': 'js_evaluation', 'attempt': attempt + 1}
                        }
                    else:
                        print(f"   ⚠️  Attempt {attempt + 1}/6: Page evaluation failed: {e}")
            
            # ✅ CRITICAL FIX: Bu if artık for loop'un DIŞINDA!
            if not email_input_ready:
                print("   🔴 FAILED: Email input did not appear after 30 seconds!")
                print("   🔴 This indicates JavaScript is NOT executing at all!")
                print("   🔴 Possible reasons:")
                print("      - Proxy is blocking JavaScript files")
                print("      - Bot detection preventing JS execution")
                print("      - VFS changed their anti-bot system")
                
                # Save debug screenshot
                try:
                    await page.screenshot(path='/tmp/vfs_js_failed.png', full_page=True)
                    print("   📸 Debug screenshot saved: /tmp/vfs_js_failed.png")
                except:
                    pass
                
                return {
                    'success': False,
                    'message': 'JavaScript execution failed - email input never appeared after 30s wait',
                    'otp_method': 'failed',
                    'debug': {
                        'stage': 'javascript_timeout',
                        'waited_seconds': 30,
                        'selectors_tried': email_selectors_to_try
                    }
                }
        
        # Verify form is now loaded
        try:
            form_check = await page.evaluate("""
                () => {
                    const emailInputs = document.querySelectorAll('input[type="email"], input[name="email"]');
                    const bodyText = document.body ? document.body.innerText : '';
                    return {
                        has_email_input: emailInputs.length > 0,
                        body_text_length: bodyText.length,
                        input_count: emailInputs.length
                    };
                }
            """)
            print(f"   📋 Form Check After JS Wait:")
            print(f"      Has Email Input: {form_check['has_email_input']}")
            print(f"      Body Text Length: {form_check['body_text_length']} chars")
            print(f"      Email Input Count: {form_check['input_count']}")
            
            if not form_check['has_email_input']:
                print("   🔴 WARNING: Form check shows no email input!")
                
        except Exception as e:
            print(f"   ⚠️  Form check failed: {e}")
        
        print("✅ JavaScript hydration complete")
        
        # DEBUG: Take screenshot AND encode as base64 for logging
        try:
            screenshot_path = '/tmp/vfs_login_page.png'
            await page.screenshot(path=screenshot_path)
            print(f"📸 Screenshot saved: {screenshot_path}")
            
            # Also encode as base64 so we can see it in logs
            import base64
            with open(screenshot_path, 'rb') as f:
                screenshot_base64 = base64.b64encode(f.read()).decode()
                print(f"📸 Screenshot Base64 (first 200 chars): {screenshot_base64[:200]}...")
                print(f"📸 Screenshot length: {len(screenshot_base64)} characters")
        except Exception as e:
            print(f"⚠️  Could not save screenshot: {e}")
        
        # DEBUG: Get page HTML content
        try:
            page_html = await page.content()
            print(f"📄 Page HTML length: {len(page_html)} characters")
            print(f"📄 Page HTML preview (first 1000 chars):")
            print(page_html[:1000])
            
            # Check for common bot detection indicators
            html_lower = page_html.lower()
            
            if 'cloudflare' in html_lower:
                print("ℹ️  Cloudflare detected (normal with proxy)")
            
            if 'verify you are human' in html_lower or 'turnstile' in html_lower:
                print("⚠️  CAPTCHA/TURNSTILE DETECTED!")
            
            if 'access denied' in html_lower or '403' in html_lower:
                print("⚠️  ACCESS DENIED detected!")
            
            if 'bot' in html_lower and 'detected' in html_lower:
                print("⚠️  BOT DETECTION message found!")
            
            if 'maintenance' in html_lower or 'bakım' in html_lower:
                print("⚠️  MAINTENANCE MODE detected in HTML!")
        except Exception as e:
            print(f"⚠️  Could not get page HTML: {e}")
        
        # DEBUG: Page info
        try:
            print(f"📄 Page title: {await page.title()}")
            print(f"📄 Current URL: {page.url}")
            
            # Check if we got redirected
            if 'login' not in page.url.lower():
                print(f"⚠️  REDIRECTED! Expected /login but got: {page.url}")
        except Exception as e:
            print(f"⚠️  Could not get page info: {e}")
        
        # Handle COOKIE CONSENT if present
        print("🍪 Checking for cookie consent...")
        cookie_selectors = [
            'button:has-text("Kabul Et")',
            'button:has-text("Hepsini Kabul Et")',
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            '#onetrust-accept-btn-handler',
        ]
        
        for selector in cookie_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    print(f"✅ Found cookie button: {selector}")
                    await click_with_human_behavior(page, selector)
                    await human_like_delay(1000, 2000)
                    print("✅ Cookie accepted")
                    break
            except Exception as e:
                # ✅ IMPROVED: Check if page closed during cookie handling
                if 'closed' in str(e).lower() or 'target' in str(e).lower():
                    print(f"🔴 Page closed during cookie consent check!")
                    return {
                        'success': False,
                        'message': f'Page closed during cookie consent: {str(e)}',
                        'otp_method': 'failed',
                        'debug': {'stage': 'cookie_consent'}
                    }
                else:
                    print(f"⚠️  Cookie consent error: {e}")
                    continue
        
        # 2. Fill login form
        print("📧 Step 2/5: Entering email and password")
        
        # Email field
        email_selectors = [
            'input[type=\"email\"]',
            'input[name=\"email\"]',
            'input[id=\"email\"]',
            '#mat-input-0',  # Common Angular Material ID
        ]
        
        email_found = False
        for selector in email_selectors:
            try:
                # ✅ IMPROVED: Check visibility before typing
                if await page.locator(selector).is_visible():
                    await human_like_typing(page, selector, email)
                    print(f"✅ Email entered via {selector}")
                    email_found = True
                    break
            except Exception as e:
                print(f"⚠️  Could not enter email via {selector}: {e}")
                # ✅ IMPROVED: Check if page closed
                if 'closed' in str(e).lower() or 'target' in str(e).lower():
                    return {
                        'success': False,
                        'message': f'Page closed during email input: {str(e)}',
                        'otp_method': 'failed',
                        'debug': {'stage': 'email_input', 'selector': selector}
                    }
                continue
        
        if not email_found:
            print("❌ Could not find email input field")
            print("   This could mean:")
            print("   1. Page is redirecting (already logged in?)")
            print("   2. Maintenance mode blocking form")
            print("   3. Bot detection blocking access")
            print("   4. Page structure changed")
            print("   CHECK THE HTML OUTPUT ABOVE FOR CLUES!")
            
            # Take additional screenshot for debugging
            try:
                error_screenshot = '/tmp/vfs_login_error.png'
                await page.screenshot(path=error_screenshot, full_page=True)
                print(f"📸 Error screenshot saved: {error_screenshot}")
            except:
                pass
            
            return {
                'success': False,
                'message': 'Email input field not found',
                'otp_method': 'failed',
                'debug': {
                    'stage': 'email_field_not_found',
                    'selectors_tried': email_selectors
                }
            }
        
        await human_like_delay(500, 1000)
        
        # Password field
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[id="password"]',
            '#mat-input-1',  # Common Angular Material ID
        ]
        
        for selector in password_selectors:
            try:
                # ✅ IMPROVED: Check visibility before typing
                if await page.locator(selector).is_visible():
                    await human_like_typing(page, selector, password)
                    print(f"✅ Password entered via {selector}")
                    break
            except Exception as e:
                print(f"⚠️  Could not enter password via {selector}: {e}")
                # ✅ IMPROVED: Check if page closed
                if 'closed' in str(e).lower() or 'target' in str(e).lower():
                    return {
                        'success': False,
                        'message': f'Page closed during password input: {str(e)}',
                        'otp_method': 'failed',
                        'debug': {'stage': 'password_input', 'selector': selector}
                    }
                continue
        
        await human_like_delay(1000, 2000)
        
        # Submit login
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Sign In")',
            'button:has-text("Giriş")',
            '.login-button',
        ]
        
        for selector in submit_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    print("🚀 Step 3/5: Submitting login form")
                    await click_with_human_behavior(page, selector)
                    break
            except Exception as e:
                print(f"⚠️  Submit button error: {e}")
                if 'closed' in str(e).lower():
                    return {
                        'success': False,
                        'message': f'Page closed during form submit: {str(e)}',
                        'otp_method': 'failed',
                        'debug': {'stage': 'form_submit'}
                    }
                continue
        
        # Wait for OTP page
        await page.wait_for_load_state('networkidle', timeout=10000)
        await human_like_delay(2000, 3000)
        
        print("📱 Step 4/5: OTP verification required")
        
        # 3. Get OTP
        otp_code = None
        otp_method = 'failed'
        
        # Try auto-reading from email
        if email_credentials and email_credentials.get('email_address'):
            print("📧 Attempting to read OTP from email...")
            
            try:
                otp_code = read_otp_from_email(
                    email_address=email_credentials['email_address'],
                    email_password=email_credentials['email_password'],  # Should be decrypted
                    imap_server=email_credentials.get('imap_server', 'imap.gmail.com'),
                    imap_port=email_credentials.get('imap_port', 993),
                    timeout_seconds=120,  # ✅ 30s → 120s (2 dakika)
                    from_domain='vfsglobal.com'
                )
                
                if otp_code:
                    print(f"✅ OTP auto-read: {otp_code}")
                    otp_method = 'auto'
                else:
                    print("⚠️  OTP email not received within timeout")
            except Exception as e:
                print(f"❌ Error reading OTP from email: {e}")
        
        # Fallback to manual input
        if not otp_code:
            print("⚠️  Falling back to manual OTP input")
            otp_code = await wait_for_otp_manual(timeout_seconds=120)
            otp_method = 'manual'
        
        if not otp_code:
            return {
                'success': False,
                'message': 'OTP not provided',
                'otp_method': otp_method,
                'debug': {'stage': 'otp_not_provided'}
            }
        
        # 4. Enter OTP
        print("🔢 Step 5/5: Entering OTP")
        
        otp_selectors = [
            'input[type="text"][maxlength="6"]',
            'input[name="otp"]',
            'input[id="otp"]',
            'input[placeholder*="OTP"]',
            'input[placeholder*="code"]',
        ]
        
        for selector in otp_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    await human_like_typing(page, selector, otp_code)
                    print(f"✅ OTP entered via {selector}")
                    break
            except Exception as e:
                print(f"⚠️  OTP input error: {e}")
                if 'closed' in str(e).lower():
                    return {
                        'success': False,
                        'message': f'Page closed during OTP input: {str(e)}',
                        'otp_method': otp_method,
                        'debug': {'stage': 'otp_input'}
                    }
                continue
        
        await human_like_delay(500, 1000)
        
        # Submit OTP
        verify_selectors = [
            'button[type="submit"]',
            'button:has-text("Verify")',
            'button:has-text("Doğrula")',
            'button:has-text("Submit")',
        ]
        
        for selector in verify_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    print("✅ Submitting OTP")
                    await click_with_human_behavior(page, selector)
                    break
            except Exception as e:
                print(f"⚠️  OTP submit error: {e}")
                if 'closed' in str(e).lower():
                    return {
                        'success': False,
                        'message': f'Page closed during OTP submit: {str(e)}',
                        'otp_method': otp_method,
                        'debug': {'stage': 'otp_submit'}
                    }
                continue
        
        # Wait for redirect to dashboard
        await page.wait_for_load_state('networkidle', timeout=15000)
        await human_like_delay(2000, 3000)
        
        # Check if login successful (look for dashboard elements)
        success_indicators = [
            'text="Dashboard"',
            'text="Yeni Rezervasyon"',
            'text="New Reservation"',
            '.dashboard',
            'a[href*="dashboard"]',
        ]
        
        login_success = False
        for indicator in success_indicators:
            if await page.locator(indicator).count() > 0:
                login_success = True
                break
        
        if login_success:
            print("✅ LOGIN SUCCESSFUL!")
            return {
                'success': True,
                'message': 'Login successful',
                'otp_method': otp_method
            }
        else:
            print("❌ Login failed - dashboard not found")
            return {
                'success': False,
                'message': 'Login failed - could not reach dashboard',
                'otp_method': otp_method,
                'debug': {'stage': 'dashboard_not_found'}
            }
        
    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        print(f"📋 Traceback:\n{traceback.format_exc()}")
        return {
            'success': False,
            'message': f'Login error: {str(e)}',
            'otp_method': 'failed',
            'debug': {'stage': 'exception', 'error': str(e)}
        }


async def ensure_logged_in(
    context: BrowserContext,
    user_id: str,
    vfs_credentials: dict,
    email_credentials: dict = None,
    session_data: dict = None,
) -> tuple[Page, bool]:
    """
    Ensure user is logged in - either restore session or perform fresh login
    
    Args:
        context: Browser context
        user_id: User ID
        vfs_credentials: VFS account credentials
        email_credentials: Email credentials for OTP
        session_data: Existing session data (if any)
        
    Returns:
        (page, is_new_login)
    """
    page = await context.new_page()
    await stealth_async(page)
    
    # ✅ CRITICAL FIX: Set context-level timeouts
    print("⚙️  Setting context-level timeouts (2 minutes)...")
    context.set_default_timeout(120000)  # 2 dakika
    context.set_default_navigation_timeout(120000)  # 2 dakika
    
    # Try to restore session
    if session_data and is_session_valid(session_data):
        print("🔄 Attempting to restore session...")
        
        session_loaded = await load_session(context, session_data)
        
        if session_loaded:
            # Navigate to dashboard to verify session
            country_code = vfs_credentials.get('country_code', 'nld')
            if not country_code:
                print("⚠️  No country_code in credentials, defaulting to 'nld'")
                country_code = 'nld'
            
            dashboard_url = f"https://visa.vfsglobal.com/tur/tr/{country_code.lower()}/dashboard"
            
            await page.goto(dashboard_url, wait_until='networkidle', timeout=15000)
            
            # Check if still logged in
            if await page.locator('text="Dashboard"').count() > 0 or \
               await page.locator('text="Yeni Rezervasyon"').count() > 0:
                print("✅ Session restored successfully")
                return page, False
            else:
                print("⚠️  Session expired, performing fresh login")
    
    # Fresh login required
    print("🔐 Performing fresh login...")
    
    # Decrypt password (in production, use proper decryption)
    password = vfs_credentials.get('password', '')
    
    login_result = await login_to_vfs(
        page=page,
        email=vfs_credentials.get('email', ''),
        password=password,
        country_code=vfs_credentials.get('country_code', 'nld'),
        email_credentials=email_credentials,
    )
    
    if not login_result['success']:
        raise Exception(f"Login failed: {login_result['message']}")
    
    print(f"✅ Fresh login successful (OTP method: {login_result['otp_method']})")
    
    # Save new session (country-specific)
    country_code = vfs_credentials.get('country_code', 'nld')
    new_session = await save_session(context, user_id, country_code, expires_hours=24)
    
    return page, True
