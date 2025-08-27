"""Kwork scraper using Playwright."""

import asyncio
import hashlib
import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, Browser, Page
from dotenv import load_dotenv

from storage.database import Database

load_dotenv()

# Configuration
KWORK_LOGIN = os.getenv("KWORK_LOGIN")
KWORK_PASSWORD = os.getenv("KWORK_PASSWORD")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
PLAYWRIGHT_PROXY = os.getenv("PLAYWRIGHT_PROXY")


class KworkScraper:
    """Kwork scraper with Playwright automation."""

    def __init__(self, db: Database):
        self.db = db
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        self.last_scan_time = None
        self.scan_interval = 45  # seconds
        self.jitter_range = (0.7, 1.3)  # 30% jitter
        
        # Kwork URLs
        self.base_url = "https://kwork.ru"
        self.login_url = "https://kwork.ru/login"
        self.orders_url = "https://kwork.ru/projects"
        
        # Selectors (may need updates if Kwork changes layout)
        self.selectors = {
            "login_email": "input[name='email']",
            "login_password": "input[name='password']",
            "login_button": "button[type='submit']",
            "order_cards": ".card-body",  # Update based on actual Kwork layout
            "order_title": "h3 a",  # Update based on actual Kwork layout
            "order_budget": ".budget",  # Update based on actual Kwork layout
            "order_category": ".category",  # Update based on actual Kwork layout
            "order_description": ".description",  # Update based on actual Kwork layout
            "order_time": ".time",  # Update based on actual Kwork layout
            "reply_form": "form[action*='reply']",  # Update based on actual Kwork layout
            "reply_textarea": "textarea[name='message']",  # Update based on actual Kwork layout
            "reply_submit": "button[type='submit']",  # Update based on actual Kwork layout
            "captcha": ".captcha, .g-recaptcha",  # Update based on actual Kwork layout
        }

    async def start(self):
        """Start the scraper."""
        self.playwright = await async_playwright().start()
        
        # Launch browser
        browser_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor"
        ]
        
        if PLAYWRIGHT_PROXY:
            self.browser = await self.playwright.chromium.launch(
                headless=PLAYWRIGHT_HEADLESS,
                args=browser_args,
                proxy={"server": PLAYWRIGHT_PROXY}
            )
        else:
            self.browser = await self.playwright.chromium.launch(
                headless=PLAYWRIGHT_HEADLESS,
                args=browser_args
            )
        
        # Create new page
        self.page = await self.browser.new_page()
        
        # Set user agent
        await self.page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        
        # Load saved session if exists
        await self.load_session()
        
        print("🚀 Kwork scraper started")

    async def stop(self):
        """Stop the scraper."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        print("🛑 Kwork scraper stopped")

    async def load_session(self):
        """Load saved session from database."""
        session_data = await self.db.get_session("kwork_session")
        if session_data:
            try:
                await self.page.context.add_cookies(json.loads(session_data))
                # Test if session is still valid
                await self.page.goto(self.base_url)
                if await self.is_logged_in_check():
                    self.is_logged_in = True
                    print("✅ Session loaded successfully")
                    return
            except Exception as e:
                print(f"⚠️ Failed to load session: {e}")
        
        print("❌ No valid session found")

    async def save_session(self):
        """Save current session to database."""
        try:
            cookies = await self.page.context.cookies()
            session_data = json.dumps(cookies)
            await self.db.save_session("kwork_session", session_data.encode())
            print("💾 Session saved")
        except Exception as e:
            print(f"❌ Failed to save session: {e}")

    async def login(self, email: str, password: str) -> bool:
        """Login to Kwork."""
        if not email or not password:
            print("❌ Email and password required")
            return False
        
        try:
            print("🔐 Logging in to Kwork...")
            await self.page.goto(self.login_url)
            
            # Fill login form
            await self.page.fill(self.selectors["login_email"], email)
            await self.page.fill(self.selectors["login_password"], password)
            
            # Submit form
            await self.page.click(self.selectors["login_button"])
            
            # Wait for redirect or error
            await self.page.wait_for_load_state("networkidle")
            
            # Check if login successful
            if await self.is_logged_in_check():
                self.is_logged_in = True
                await self.save_session()
                print("✅ Login successful")
                return True
            else:
                print("❌ Login failed")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

    async def is_logged_in_check(self) -> bool:
        """Check if user is logged in."""
        try:
            # Check for logout link or user menu
            logout_link = await self.page.query_selector("a[href*='logout']")
            user_menu = await self.page.query_selector(".user-menu, .profile")
            return logout_link is not None or user_menu is not None
        except:
            return False

    async def check_captcha(self) -> bool:
        """Check if captcha is present."""
        try:
            captcha_element = await self.page.query_selector(self.selectors["captcha"])
            return captcha_element is not None
        except:
            return False

    async def scan_orders(self) -> List[Dict]:
        """Scan for new orders based on filters."""
        if not self.is_logged_in:
            print("❌ Not logged in")
            return []
        
        try:
            print("🔍 Scanning for new orders...")
            await self.page.goto(self.orders_url)
            await self.page.wait_for_load_state("networkidle")
            
            # Check for captcha
            if await self.check_captcha():
                print("⚠️ Captcha detected!")
                return []
            
            # Get order cards
            order_cards = await self.page.query_selector_all(self.selectors["order_cards"])
            
            orders = []
            for card in order_cards:
                try:
                    order_data = await self.parse_order_card(card)
                    if order_data:
                        orders.append(order_data)
                except Exception as e:
                    print(f"⚠️ Error parsing order card: {e}")
                    continue
            
            print(f"📊 Found {len(orders)} orders")
            return orders
            
        except Exception as e:
            print(f"❌ Error scanning orders: {e}")
            return []

    async def parse_order_card(self, card) -> Optional[Dict]:
        """Parse order card element."""
        try:
            # Extract order data (update selectors based on actual Kwork layout)
            title_element = await card.query_selector(self.selectors["order_title"])
            title = await title_element.text_content() if title_element else ""
            
            url_element = await card.query_selector(self.selectors["order_title"])
            url = await url_element.get_attribute("href") if url_element else ""
            if url and not url.startswith("http"):
                url = urljoin(self.base_url, url)
            
            budget_element = await card.query_selector(self.selectors["order_budget"])
            budget_text = await budget_element.text_content() if budget_element else ""
            budget = self.extract_budget(budget_text)
            
            category_element = await card.query_selector(self.selectors["order_category"])
            category = await category_element.text_content() if category_element else ""
            
            description_element = await card.query_selector(self.selectors["order_description"])
            description = await description_element.text_content() if description_element else ""
            
            time_element = await card.query_selector(self.selectors["order_time"])
            time_text = await time_element.text_content() if time_element else ""
            
            # Generate order ID
            order_id = self.generate_order_id(url, title, time_text)
            
            return {
                "id": order_id,
                "title": title.strip(),
                "url": url,
                "budget": budget,
                "category": category.strip(),
                "description": description.strip(),
                "time": time_text.strip(),
                "scanned_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ Error parsing order card: {e}")
            return None

    def extract_budget(self, budget_text: str) -> Optional[int]:
        """Extract budget amount from text."""
        try:
            # Remove non-numeric characters except digits
            import re
            numbers = re.findall(r'\d+', budget_text.replace(' ', ''))
            if numbers:
                return int(numbers[0])
        except:
            pass
        return None

    def generate_order_id(self, url: str, title: str, time_text: str) -> str:
        """Generate unique order ID."""
        content = f"{url}{title}{time_text}"
        return hashlib.md5(content.encode()).hexdigest()

    async def apply_filters(self, orders: List[Dict]) -> List[Dict]:
        """Apply filters to orders."""
        filters = await self.db.get_filters()
        if not filters:
            return orders
        
        filtered_orders = []
        
        for order in orders:
            for filter_data in filters:
                if self.matches_filter(order, filter_data):
                    order["matched_filter"] = filter_data["name"]
                    filtered_orders.append(order)
                    break
        
        return filtered_orders

    def matches_filter(self, order: Dict, filter_data: Dict) -> bool:
        """Check if order matches filter criteria."""
        # Keywords check
        if "keywords_any" in filter_data:
            keywords = filter_data["keywords_any"]
            text = f"{order['title']} {order['description']}".lower()
            if not any(keyword.lower() in text for keyword in keywords):
                return False
        
        if "keywords_not" in filter_data:
            keywords = filter_data["keywords_not"]
            text = f"{order['title']} {order['description']}".lower()
            if any(keyword.lower() in text for keyword in keywords):
                return False
        
        # Budget check
        if "budget_min" in filter_data and order.get("budget"):
            if order["budget"] < filter_data["budget_min"]:
                return False
        
        if "budget_max" in filter_data and order.get("budget"):
            if order["budget"] > filter_data["budget_max"]:
                return False
        
        # Category check
        if "categories" in filter_data:
            if order.get("category") not in filter_data["categories"]:
                return False
        
        # Language check
        if "lang" in filter_data:
            # Simple language detection (can be improved)
            text = f"{order['title']} {order['description']}"
            if "lang" in filter_data and "ru" in filter_data["lang"]:
                # Check for Cyrillic characters
                if not any(ord(char) > 127 for char in text):
                    return False
        
        # Minimum words check
        if "min_words" in filter_data:
            word_count = len(order.get("description", "").split())
            if word_count < filter_data["min_words"]:
                return False
        
        return True

    async def send_reply(self, order_url: str, template_name: str) -> bool:
        """Send reply to order using template."""
        if not self.is_logged_in:
            print("❌ Not logged in")
            return False
        
        try:
            print(f"📝 Sending reply to {order_url}")
            
            # Navigate to order page
            await self.page.goto(order_url)
            await self.page.wait_for_load_state("networkidle")
            
            # Check for captcha
            if await self.check_captcha():
                print("⚠️ Captcha detected during reply!")
                return False
            
            # Get template
            templates = await self.db.get_templates()
            if template_name not in templates:
                print(f"❌ Template '{template_name}' not found")
                return False
            
            template_text = templates[template_name]
            
            # Fill reply form
            reply_textarea = await self.page.query_selector(self.selectors["reply_textarea"])
            if not reply_textarea:
                print("❌ Reply form not found")
                return False
            
            await reply_textarea.fill(template_text)
            
            # Submit form
            submit_button = await self.page.query_selector(self.selectors["reply_submit"])
            if submit_button:
                await submit_button.click()
                await self.page.wait_for_load_state("networkidle")
                
                # Check for success/error
                success = await self.check_reply_success()
                if success:
                    print("✅ Reply sent successfully")
                    return True
                else:
                    print("❌ Reply failed")
                    return False
            else:
                print("❌ Submit button not found")
                return False
                
        except Exception as e:
            print(f"❌ Error sending reply: {e}")
            return False

    async def check_reply_success(self) -> bool:
        """Check if reply was sent successfully."""
        try:
            # Look for success message or error
            success_msg = await self.page.query_selector(".success, .alert-success")
            error_msg = await self.page.query_selector(".error, .alert-danger")
            
            return success_msg is not None and error_msg is None
        except:
            return False

    async def run_monitoring_loop(self):
        """Main monitoring loop."""
        while True:
            try:
                if not self.is_logged_in:
                    print("⚠️ Not logged in, skipping scan")
                    await asyncio.sleep(60)
                    continue
                
                # Scan for orders
                orders = await self.scan_orders()
                
                # Apply filters
                filtered_orders = await self.apply_filters(orders)
                
                # Check for new orders
                new_orders = []
                for order in filtered_orders:
                    if not await self.db.is_order_seen(order["id"]):
                        new_orders.append(order)
                        await self.db.add_order_seen(order["id"], order["title"], order["url"])
                
                if new_orders:
                    print(f"🎉 Found {len(new_orders)} new orders!")
                    # TODO: Send notifications to bot
                
                # Update last scan time
                self.last_scan_time = datetime.now()
                
                # Calculate next scan interval with jitter
                jitter = random.uniform(*self.jitter_range)
                interval = int(self.scan_interval * jitter)
                
                print(f"⏰ Next scan in {interval} seconds")
                await asyncio.sleep(interval)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait before retry
