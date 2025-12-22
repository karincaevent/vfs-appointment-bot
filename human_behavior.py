"""
Human Behavior Simulation Module
Mimics real human interactions to avoid bot detection
"""
import asyncio
import random
from typing import List
from playwright.async_api import Page


class HumanBehavior:
    """Simulates human-like behavior patterns"""
    
    # User-Agent pool (rotated randomly)
    USER_AGENTS = [
        # Chrome on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        
        # Chrome on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        
        # Firefox on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        
        # Safari on macOS
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        
        # Edge on Windows
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    ]
    
    @staticmethod
    def get_random_user_agent() -> str:
        """Get a random User-Agent string"""
        return random.choice(HumanBehavior.USER_AGENTS)
    
    @staticmethod
    async def random_delay(min_ms: int, max_ms: int):
        """
        Random delay in milliseconds
        
        Args:
            min_ms: Minimum delay in milliseconds
            max_ms: Maximum delay in milliseconds
        """
        delay_sec = random.uniform(min_ms, max_ms) / 1000
        await asyncio.sleep(delay_sec)
    
    @staticmethod
    async def simulate_page_load_wait():
        """Simulate waiting for page to load (2-4 seconds)"""
        await HumanBehavior.random_delay(2000, 4000)
    
    @staticmethod
    async def simulate_reading_content():
        """Simulate reading content on page (3-6 seconds)"""
        await HumanBehavior.random_delay(3000, 6000)
    
    @staticmethod
    async def simulate_thinking():
        """Simulate human thinking/decision time (1-2.5 seconds)"""
        await HumanBehavior.random_delay(1000, 2500)
    
    @staticmethod
    async def simulate_typing_delay():
        """Simulate typing a single character (50-150ms)"""
        await HumanBehavior.random_delay(50, 150)
    
    @staticmethod
    async def simulate_form_field(page: Page, selector: str, text: str):
        """
        Simulate human typing into a form field
        
        Args:
            page: Playwright page object
            selector: CSS selector for input field
            text: Text to type
        """
        try:
            # Click on field
            await page.click(selector)
            await HumanBehavior.random_delay(200, 400)
            
            # Type character by character with human-like delays
            for char in text:
                await page.type(selector, char)
                await HumanBehavior.simulate_typing_delay()
            
            # Small pause after finishing
            await HumanBehavior.random_delay(300, 600)
        except Exception as e:
            print(f"⚠️  Could not simulate typing in field {selector}: {str(e)}")
    
    @staticmethod
    async def simulate_mouse_movement(page: Page, x: int = None, y: int = None):
        """
        Simulate natural mouse movement
        
        Args:
            page: Playwright page object
            x: Target X coordinate (random if None)
            y: Target Y coordinate (random if None)
        """
        try:
            if x is None:
                x = random.randint(100, 800)
            if y is None:
                y = random.randint(100, 600)
            
            # Move mouse to position
            await page.mouse.move(x, y)
            await HumanBehavior.random_delay(100, 300)
        except Exception as e:
            print(f"⚠️  Mouse movement failed: {str(e)}")
    
    @staticmethod
    async def simulate_scrolling(page: Page):
        """
        Simulate human-like scrolling behavior
        """
        try:
            # Scroll down a bit
            scroll_amount = random.randint(200, 500)
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await HumanBehavior.random_delay(500, 1000)
            
            # Maybe scroll back up
            if random.random() < 0.3:  # 30% chance
                await page.evaluate(f'window.scrollBy(0, -{scroll_amount // 2})')
                await HumanBehavior.random_delay(300, 600)
        except Exception as e:
            print(f"⚠️  Scrolling failed: {str(e)}")
    
    @staticmethod
    async def simulate_cookie_banner_interaction(page: Page):
        """
        Simulate interacting with cookie/GDPR banners
        Common selectors for accept buttons
        """
        cookie_selectors = [
            'button:has-text("Accept")',
            'button:has-text("Kabul")',
            'button:has-text("Tamam")',
            'button:has-text("OK")',
            '#accept-cookies',
            '.accept-cookies',
            '[data-action="accept"]',
            '.cookie-accept',
        ]
        
        for selector in cookie_selectors:
            try:
                # Check if button exists
                if await page.locator(selector).count() > 0:
                    print(f"🍪 Found cookie banner, accepting...")
                    await HumanBehavior.simulate_thinking()  # Think before clicking
                    await page.click(selector)
                    await HumanBehavior.random_delay(500, 1000)
                    print(f"✅ Cookie banner accepted")
                    break
            except Exception:
                continue
    
    @staticmethod
    async def simulate_full_page_interaction(page: Page):
        """
        Simulate a full human page interaction sequence
        - Wait for page load
        - Accept cookies
        - Scroll a bit
        - Move mouse randomly
        - Read content
        """
        print("👤 Simulating human page interaction...")
        
        # 1. Initial page load wait
        await HumanBehavior.simulate_page_load_wait()
        
        # 2. Try to accept cookie banner
        await HumanBehavior.simulate_cookie_banner_interaction(page)
        
        # 3. Random mouse movements
        for _ in range(random.randint(2, 4)):
            await HumanBehavior.simulate_mouse_movement(page)
        
        # 4. Scroll behavior
        if random.random() < 0.7:  # 70% chance to scroll
            await HumanBehavior.simulate_scrolling(page)
        
        # 5. "Reading" the content
        await HumanBehavior.simulate_reading_content()
        
        print("✅ Human interaction simulation complete")
    
    @staticmethod
    def get_random_country_scan_delay() -> int:
        """
        Get random delay between scanning different countries
        Returns delay in milliseconds
        
        Real humans don't check multiple countries rapidly.
        They would take 2-5 minutes between checking different countries.
        """
        # 2-5 minutes in milliseconds
        min_delay = 2 * 60 * 1000  # 2 minutes
        max_delay = 5 * 60 * 1000  # 5 minutes
        return random.randint(min_delay, max_delay)
    
    @staticmethod
    def get_random_scan_interval() -> int:
        """
        Get random interval for periodic scanning
        Returns interval in seconds
        
        Instead of scanning every 5 minutes exactly (robotic),
        vary between 4-7 minutes for more natural pattern.
        """
        min_interval = 4 * 60  # 4 minutes
        max_interval = 7 * 60  # 7 minutes
        return random.randint(min_interval, max_interval)
