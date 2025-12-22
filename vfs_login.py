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
    logger.warning(f"⏳ Manual OTP input required (timeout: {timeout_seconds}s)")
    logger.warning("   VFS will send OTP to registered email")
    logger.warning("   This is a fallback - configure email credentials for auto OTP")
    
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
    2. Check for maintenance mode and bot detection
    3. Enter email and password
    4. Read OTP from email (or wait for manual input)
    5. Enter OTP and verify
    6. Navigate to dashboard
    
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
            'otp_method': 'auto' | 'manual' | 'failed' | 'maintenance'
        }
    """
    try:
        # Go DIRECTLY to login page, not homepage!
        # URL Format: https://visa.vfsglobal.com/tur/tr/nld/login
        login_url = f"https://visa.vfsglobal.com/tur/tr/{country_code.lower()}/login"
        
        logger.info(f"🌍 Navigating DIRECTLY to login page: {login_url}")
        logger.info("   Skipping homepage to avoid button detection issues")
        
        # Apply stealth
        await stealth_async(page)
        
        # 1. Go to login page
        try:
            await page.goto(login_url, wait_until='networkidle', timeout=30000)
            logger.info("✅ Login page loaded")
        except Exception as e:
            logger.error(f"❌ Could not load login page: {e}")
            return {
                'success': False,
                'message': f'Login page load failed: {str(e)}',
                'otp_method': 'failed'
            }
        
        # Wait for page to settle
        await human_like_delay(2000, 4000)
        
        logger.info("📍 Step 1/6: Login page ready")
        
        # ===== DEBUG SECTION: CRITICAL FOR DIAGNOSING ISSUES =====
        
        # DEBUG: Take screenshot AND encode as base64 for logging
        try:
            screenshot_path = '/tmp/vfs_login_page.png'
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
            
            # Also encode as base64 so we can see it in logs
            import base64
            with open(screenshot_path, 'rb') as f:
                screenshot_base64 = base64.b64encode(f.read()).decode()
                logger.info(f"📸 Screenshot Base64 (first 200 chars): {screenshot_base64[:200]}...")
                logger.info(f"📸 Screenshot length: {len(screenshot_base64)} characters")
        except Exception as e:
            logger.warning(f"Could not save screenshot: {e}")
        
        # DEBUG: Get page HTML content
        try:
            page_html = await page.content()
            logger.info(f"📄 Page HTML length: {len(page_html)} characters")
            logger.info(f"📄 Page HTML preview (first 1000 chars):")
            logger.info(page_html[:1000])
            
            # Check for common bot detection indicators
            html_lower = page_html.lower()
            
            if 'cloudflare' in html_lower:
                logger.warning("⚠️  CLOUDFLARE DETECTED in page HTML!")
                logger.warning("   This indicates bot protection is active")
                logger.warning("   Solution: Use residential proxy")
            
            if 'verify you are human' in html_lower or 'turnstile' in html_lower:
                logger.warning("⚠️  CAPTCHA/TURNSTILE DETECTED!")
                logger.warning("   VFS is showing CAPTCHA challenge")
                logger.warning("   Solution: Residential proxy + CAPTCHA solver")
            
            if 'access denied' in html_lower or '403' in html_lower:
                logger.warning("⚠️  ACCESS DENIED detected!")
                logger.warning("   Railway IP is blocked by VFS")
                logger.warning("   Solution: Use residential proxy")
            
            if 'bot' in html_lower and 'detected' in html_lower:
                logger.warning("⚠️  BOT DETECTION message found!")
                logger.warning("   VFS detected automated access")
            
            if 'maintenance' in html_lower or 'bakım' in html_lower:
                logger.warning("⚠️  MAINTENANCE MODE detected in HTML!")
                logger.warning("   VFS system is under maintenance")
                return {
                    'success': False,
                    'message': 'VFS system maintenance in progress',
                    'otp_method': 'maintenance'
                }
        except Exception as e:
            logger.warning(f"Could not get page HTML: {e}")
        
        # DEBUG: Page info
        try:
            page_title = await page.title()
            current_url = page.url
            
            logger.info(f"📄 Page title: {page_title}")
            logger.info(f"📄 Current URL: {current_url}")
            
            # Check if we got redirected
            if 'login' not in current_url.lower():
                logger.warning(f"⚠️  REDIRECTED! Expected /login but got: {current_url}")
                
                if 'dashboard' in current_url.lower():
                    logger.info("✅ Already logged in! Redirected to dashboard")
                    return {
                        'success': True,
                        'message': 'Already logged in',
                        'otp_method': 'session'
                    }
                elif 'maintenance' in current_url.lower():
                    logger.warning("⚠️  Redirected to maintenance page")
                    return {
                        'success': False,
                        'message': 'VFS maintenance mode',
                        'otp_method': 'maintenance'
                    }
        except Exception as e:
            logger.warning(f"Could not get page info: {e}")
        
        # ===== END DEBUG SECTION =====
        
        # CHECK FOR MAINTENANCE MODE (CRITICAL!)
        logger.info("🔍 Step 2/6: Checking for maintenance mode...")
        maintenance_selectors = [
            'text="Sistem Bakımı"',
            'text="Planlanmış Sistem Bakımı"',
            'text="Maintenance"',
            'text="System Maintenance"',
            'text="bakım nedeniyle"',
            'text="temporarily unavailable"',
        ]
        
        for selector in maintenance_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    logger.warning("⚠️  VFS IS IN MAINTENANCE MODE!")
                    logger.warning("   System is temporarily unavailable")
                    logger.warning("   Bot will retry on next scan")
                    return {
                        'success': False,
                        'message': 'VFS system maintenance in progress',
                        'otp_method': 'maintenance'
                    }
            except:
                continue
        
        logger.info("✅ No maintenance mode detected")
        
        # Handle COOKIE CONSENT if present
        logger.info("🍪 Step 3/6: Checking for cookie consent...")
        cookie_selectors = [
            'button:has-text("Kabul Et")',
            'button:has-text("Hepsini Kabul Et")',
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            'button:has-text("kapatmak")',  # From screenshot: "kapatmak" button
            '#onetrust-accept-btn-handler',
        ]
        
        cookie_handled = False
        for selector in cookie_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    logger.info(f"✅ Found cookie/banner button: {selector}")
                    await click_with_human_behavior(page, selector)
                    await human_like_delay(1000, 2000)
                    logger.info("✅ Banner closed")
                    cookie_handled = True
                    break
            except:
                continue
        
        if not cookie_handled:
            logger.info("ℹ️  No cookie popup/banner found")
        
        # Fill login form
        logger.info("📧 Step 4/6: Entering email and password")
        
        # Email field
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id="email"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="e-posta" i]',
            '#mat-input-0',  # Common Angular Material ID
        ]
        
        email_entered = False
        for selector in email_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    await human_like_typing(page, selector, email)
                    logger.info(f"✅ Email entered via {selector}")
                    email_entered = True
                    break
            except Exception as e:
                logger.debug(f"Email selector {selector} failed: {e}")
                continue
        
        if not email_entered:
            logger.error("❌ Could not find email input field")
            logger.error("   This could mean:")
            logger.error("   1. Page is redirecting (already logged in?)")
            logger.error("   2. Maintenance mode blocking form")
            logger.error("   3. Bot detection blocking access")
            logger.error("   4. Page structure changed")
            logger.error("   CHECK THE HTML OUTPUT ABOVE FOR CLUES!")
            return {
                'success': False,
                'message': 'Email input field not found',
                'otp_method': 'failed'
            }
        
        await human_like_delay(500, 1000)
        
        # Password field
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[id="password"]',
            'input[placeholder*="password" i]',
            'input[placeholder*="şifre" i]',
            '#mat-input-1',  # Common Angular Material ID
        ]
        
        password_entered = False
        for selector in password_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    await human_like_typing(page, selector, password)
                    logger.info(f"✅ Password entered via {selector}")
                    password_entered = True
                    break
            except Exception as e:
                logger.debug(f"Password selector {selector} failed: {e}")
                continue
        
        if not password_entered:
            logger.error("❌ Could not find password input field")
            return {
                'success': False,
                'message': 'Password input field not found',
                'otp_method': 'failed'
            }
        
        await human_like_delay(1000, 2000)
        
        # Submit login
        logger.info("🚀 Step 5/6: Submitting login form")
        
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Sign In")',
            'button:has-text("Giriş")',
            'button:has-text("Oturum Aç")',
            '.login-button',
            '.submit-button',
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.info(f"✅ Found submit button: {selector}")
                    await click_with_human_behavior(page, selector)
                    submitted = True
                    break
            except Exception as e:
                logger.debug(f"Submit selector {selector} failed: {e}")
                continue
        
        if not submitted:
            logger.warning("⚠️  Could not find submit button, trying Enter key")
            try:
                await page.keyboard.press('Enter')
                logger.info("✅ Pressed Enter key")
            except Exception as e:
                logger.error(f"❌ Could not submit form: {e}")
                return {
                    'success': False,
                    'message': 'Submit button not found',
                    'otp_method': 'failed'
                }
        
        # Wait for OTP page
        await page.wait_for_load_state('networkidle', timeout=15000)
        await human_like_delay(2000, 3000)
        
        logger.info("📱 Step 6/6: OTP verification required")
        
        # Take screenshot after submit
        try:
            await page.screenshot(path='/tmp/vfs_after_submit.png')
            logger.info("📸 After submit screenshot: /tmp/vfs_after_submit.png")
            logger.info(f"📄 Current URL: {page.url}")
        except:
            pass
        
        # Get OTP
        otp_code = None
        otp_method = 'failed'
        
        # Try auto-reading from email
        if email_credentials and email_credentials.get('email_address'):
            logger.info("📧 Attempting to read OTP from email...")
            logger.info(f"   Email: {email_credentials.get('email_address')}")
            
            try:
                otp_code = read_otp_from_email(
                    email_address=email_credentials['email_address'],
                    email_password=email_credentials['email_password'],  # Should be decrypted
                    imap_server=email_credentials.get('imap_server', 'imap.gmail.com'),
                    imap_port=email_credentials.get('imap_port', 993),
                    timeout_seconds=60,  # Increased to 60 seconds
                    from_domain='vfsglobal.com'
                )
                
                if otp_code:
                    logger.info(f"✅ OTP auto-read: {otp_code}")
                    otp_method = 'auto'
                else:
                    logger.warning("⚠️  OTP email not received within 60 seconds")
            except Exception as e:
                logger.error(f"❌ Error reading OTP from email: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.warning("⚠️  No email credentials provided for OTP auto-read")
        
        # Fallback to manual input
        if not otp_code:
            logger.warning("⚠️  Falling back to manual OTP input")
            logger.warning("   Please check your email for OTP code")
            otp_code = await wait_for_otp_manual(timeout_seconds=120)
            otp_method = 'manual'
        
        if not otp_code:
            logger.error("❌ No OTP code provided")
            return {
                'success': False,
                'message': 'OTP not provided - check email credentials',
                'otp_method': otp_method
            }
        
        # Enter OTP
        logger.info("🔢 Entering OTP code...")
        
        otp_selectors = [
            'input[type="text"][maxlength="6"]',
            'input[type="text"][maxlength="4"]',
            'input[name="otp"]',
            'input[id="otp"]',
            'input[placeholder*="OTP" i]',
            'input[placeholder*="code" i]',
            'input[placeholder*="kod" i]',
        ]
        
        otp_entered = False
        for selector in otp_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    await human_like_typing(page, selector, otp_code)
                    logger.info(f"✅ OTP entered via {selector}")
                    otp_entered = True
                    break
            except Exception as e:
                logger.debug(f"OTP selector {selector} failed: {e}")
                continue
        
        if not otp_entered:
            logger.error("❌ Could not find OTP input field")
            return {
                'success': False,
                'message': 'OTP input field not found',
                'otp_method': otp_method
            }
        
        await human_like_delay(500, 1000)
        
        # Submit OTP
        verify_selectors = [
            'button[type="submit"]',
            'button:has-text("Verify")',
            'button:has-text("Doğrula")',
            'button:has-text("Submit")',
            'button:has-text("Gönder")',
        ]
        
        for selector in verify_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    logger.info(f"✅ Submitting OTP via {selector}")
                    await click_with_human_behavior(page, selector)
                    break
            except:
                continue
        
        # Wait for redirect to dashboard
        await page.wait_for_load_state('networkidle', timeout=20000)
        await human_like_delay(2000, 3000)
        
        # Take final screenshot
        try:
            await page.screenshot(path='/tmp/vfs_final.png')
            logger.info("📸 Final screenshot: /tmp/vfs_final.png")
            logger.info(f"📄 Final URL: {page.url}")
        except:
            pass
        
        # Check if login successful
        success_indicators = [
            'text="Dashboard"',
            'text="Başvuru Detayları"',
            'text="Yeni Rezervasyon"',
            'text="New Reservation"',
            '.dashboard',
            'a[href*="dashboard"]',
            'a[href*="application"]',
        ]
        
        login_success = False
        for indicator in success_indicators:
            count = await page.locator(indicator).count()
            if count > 0:
                login_success = True
                logger.info(f"✅ Found success indicator: {indicator}")
                break
        
        if login_success:
            logger.info("✅ LOGIN SUCCESSFUL!")
            return {
                'success': True,
                'message': 'Login successful',
                'otp_method': otp_method
            }
        else:
            logger.error("❌ Login failed - dashboard not found")
            logger.error(f"   Current URL: {page.url}")
            return {
                'success': False,
                'message': f'Login failed - current URL: {page.url}',
                'otp_method': otp_method
            }
        
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        logger.error(f"   Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Take screenshot on error
        try:
            await page.screenshot(path='/tmp/vfs_error.png')
            logger.info("📸 Error screenshot: /tmp/vfs_error.png")
        except:
            pass
        
        return {
            'success': False,
            'message': f'Login error: {str(e)}',
            'otp_method': 'failed'
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
    
    # Try to restore session
    if session_data and is_session_valid(session_data):
        logger.info("🔄 Attempting to restore session...")
        
        session_loaded = await load_session(context, session_data)
        
        if session_loaded:
            # Navigate to dashboard to verify session
            country_code = vfs_credentials.get('country_code', 'nld')
            dashboard_url = f"https://visa.vfsglobal.com/tur/tr/{country_code}/dashboard"
            
            try:
                await page.goto(dashboard_url, wait_until='networkidle', timeout=15000)
                
                # Check if still logged in
                if await page.locator('text="Dashboard"').count() > 0 or \
                   await page.locator('text="Yeni Rezervasyon"').count() > 0:
                    logger.info("✅ Session restored successfully")
                    return page, False
                else:
                    logger.warning("⚠️  Session expired, performing fresh login")
            except Exception as e:
                logger.warning(f"⚠️  Session restore failed: {e}")
    
    # Fresh login required
    logger.info("🔐 Performing fresh login...")
    
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
    
    logger.info(f"✅ Fresh login successful (OTP method: {login_result['otp_method']})")
    
    # Save new session (country-specific)
    country_code = vfs_credentials.get('country_code', 'nld')
    new_session = await save_session(context, user_id, country_code, expires_hours=24)
    
    return page, True
