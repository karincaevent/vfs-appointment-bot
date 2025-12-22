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
    1. Go to VFS homepage
    2. Click "Şimdi randevu al" (Book appointment now)
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
            'otp_method': 'auto' | 'manual' | 'failed'
        }
    """
    try:
        base_url = f"https://visa.vfsglobal.com/tur/tr/{country_code.lower()}"
        
        logger.info(f"🌍 Navigating to VFS homepage: {base_url}")
        
        # Apply stealth
        await stealth_async(page)
        
        # 1. Go to homepage
        await page.goto(base_url, wait_until='networkidle', timeout=30000)
        await human_like_delay(2000, 4000)
        
        logger.info("📍 Step 1/6: Homepage loaded")
        
        # 2. Click "Şimdi randevu al" button
        # Try multiple selectors
        book_button_selectors = [
            'text="Şimdi randevu al"',
            'text="Book an appointment"',
            'a[href*="login"]',
            'button:has-text("randevu")',
            '.appointment-button',
        ]
        
        clicked = False
        for selector in book_button_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    logger.info(f"🖱️  Step 2/6: Clicking '{selector}'")
                    await click_with_human_behavior(page, selector)
                    clicked = True
                    break
            except:
                continue
        
        if not clicked:
            logger.error("❌ Could not find 'Book appointment' button")
            return {
                'success': False,
                'message': 'Book appointment button not found',
                'otp_method': 'failed'
            }
        
        await human_like_delay(2000, 3000)
        
        # 3. Fill login form
        logger.info("📧 Step 3/6: Entering email and password")
        
        # Email field
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id="email"]',
            '#mat-input-0',  # Common Angular Material ID
        ]
        
        for selector in email_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    await human_like_typing(page, selector, email)
                    logger.info(f"✅ Email entered via {selector}")
                    break
            except:
                continue
        
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
                if await page.locator(selector).count() > 0:
                    await human_like_typing(page, selector, password)
                    logger.info(f"✅ Password entered via {selector}")
                    break
            except:
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
                    logger.info("🚀 Step 4/6: Submitting login form")
                    await click_with_human_behavior(page, selector)
                    break
            except:
                continue
        
        # Wait for OTP page
        await page.wait_for_load_state('networkidle', timeout=10000)
        await human_like_delay(2000, 3000)
        
        logger.info("📱 Step 5/6: OTP verification required")
        
        # 4. Get OTP
        otp_code = None
        otp_method = 'failed'
        
        # Try auto-reading from email
        if email_credentials and email_credentials.get('email_address'):
            logger.info("📧 Attempting to read OTP from email...")
            
            try:
                otp_code = read_otp_from_email(
                    email_address=email_credentials['email_address'],
                    email_password=email_credentials['email_password'],  # Should be decrypted
                    imap_server=email_credentials.get('imap_server', 'imap.gmail.com'),
                    imap_port=email_credentials.get('imap_port', 993),
                    timeout_seconds=30,
                    from_domain='vfsglobal.com'
                )
                
                if otp_code:
                    logger.info(f"✅ OTP auto-read: {otp_code}")
                    otp_method = 'auto'
                else:
                    logger.warning("⚠️  OTP email not received within timeout")
            except Exception as e:
                logger.error(f"❌ Error reading OTP from email: {e}")
        
        # Fallback to manual input
        if not otp_code:
            logger.warning("⚠️  Falling back to manual OTP input")
            otp_code = await wait_for_otp_manual(timeout_seconds=120)
            otp_method = 'manual'
        
        if not otp_code:
            return {
                'success': False,
                'message': 'OTP not provided',
                'otp_method': otp_method
            }
        
        # 5. Enter OTP
        logger.info("🔢 Step 6/6: Entering OTP")
        
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
                    logger.info(f"✅ OTP entered via {selector}")
                    break
            except:
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
                    logger.info("✅ Submitting OTP")
                    await click_with_human_behavior(page, selector)
                    break
            except:
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
            logger.info("✅ LOGIN SUCCESSFUL!")
            return {
                'success': True,
                'message': 'Login successful',
                'otp_method': otp_method
            }
        else:
            logger.error("❌ Login failed - dashboard not found")
            return {
                'success': False,
                'message': 'Login failed - could not reach dashboard',
                'otp_method': otp_method
            }
        
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
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
            
            await page.goto(dashboard_url, wait_until='networkidle', timeout=15000)
            
            # Check if still logged in
            if await page.locator('text="Dashboard"').count() > 0 or \
               await page.locator('text="Yeni Rezervasyon"').count() > 0:
                logger.info("✅ Session restored successfully")
                return page, False
            else:
                logger.warning("⚠️  Session expired, performing fresh login")
    
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
