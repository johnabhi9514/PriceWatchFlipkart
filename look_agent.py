# =============================================================
# look_agent.py  —  FINAL VERSION
# =============================================================
# Tested on 5 Flipkart products (April 2026):
#   Samsung S25 Ultra  ₹1,29,999  class: v1zwn29
#   iPhone 16 Pro Max  ₹1,34,900  class: v1zwn29
#   Sony PlayStation 5 ₹54,990    class: v1zwn29
#   Ustraa Beard Oil   ₹298       class: v1zwn20
#   Kalapushpi Saree   ₹484       class: v1zwn20
# =============================================================

import re
import time
import random
import logging
import platform

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from bs4 import BeautifulSoup


class LookAgent:

    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Run: pip install playwright && playwright install chromium"
            )
        # Set browser path and install if missing
        import subprocess, sys, os
        # Use /tmp for browser cache — writable on all cloud platforms
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp/ms-playwright"
        browser_path = "/tmp/ms-playwright"
        # Check if chromium binary exists anywhere in the cache
        chromium_exists = False
        if os.path.exists(browser_path):
            for root, dirs, files in os.walk(browser_path):
                if "headless_shell" in files or "chrome" in files or "chromium" in files:
                    chromium_exists = True
                    break
        if not chromium_exists:
            logger.info("LookAgent: installing chromium to /tmp/ms-playwright ...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True,
                env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "/tmp/ms-playwright"}
            )
            logger.info(f"LookAgent: install result: {result.returncode}")
            if result.stderr:
                logger.debug(f"LookAgent: {result.stderr[:300]}")
        logger.info("LookAgent: ready")

    def fetch(self, url: str) -> dict | None:
        logger.info(f"LookAgent: opening browser for {url[:60]}...")

        if platform.system() == "Windows":
            import asyncio
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        try:
            import os
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp/ms-playwright"
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--single-process",       # needed on some cloud platforms
                        "--no-zygote",            # needed on some cloud platforms
                    ]
                )

                context = browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={
                        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8",
                        "DNT": "1",
                    }
                )

                context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                page = context.new_page()

                # Visit homepage first to get session cookies
                logger.info("LookAgent: visiting homepage for cookies...")
                page.goto("https://www.flipkart.com",
                          wait_until="domcontentloaded", timeout=20000)
                time.sleep(random.uniform(1.5, 2.5))

                # Load product page
                logger.info("LookAgent: navigating to product page...")
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(random.uniform(2.0, 3.5))

                # Scroll to trigger lazy load
                page.evaluate("window.scrollTo(0, 400)")
                time.sleep(1.0)

                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, "lxml")
            price = self._extract_price(soup)
            name  = self._extract_name(soup)

            if price is None:
                with open("debug_flipkart.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.warning(
                    "LookAgent: browser loaded page but price not found. "
                    "Saved debug_flipkart.html — open in browser to inspect."
                )
                return None

            logger.info(f"LookAgent: found '{name[:50]}' at Rs.{price:,.0f}")
            return {"name": name, "price": price, "url": url}

        except Exception as e:
            logger.error(f"LookAgent: browser error: {e}")
            return None

    def _extract_price(self, soup: BeautifulSoup) -> float | None:
        """
        Extract selling price from any Flipkart product page.

        CLASS MAP (confirmed across 5 products, April 2026):
          v1zwn29 = selling/discounted price  (mobiles, electronics)
          v1zwn20 = MRP / universal price     (ALL product types)
          v1zwn22 = total with delivery       (ignore)
          v1zwn24 = recommended products      (ignore)
          v1zwn28 = recommended products      (ignore)

        LOGIC:
          For each selector, scan ALL matching elements.
          Return the FIRST one that matches: starts with ₹,
          followed only by digits and commas.
          This rejects "Get Up to ₹500 Off", "512 GB + 12 GB", etc.
        """
        # Priority order — confirmed working April 2026
        selectors = [
            "div.v1zwn29",    # discounted selling price (electronics)
            "div.v1zwn20",    # universal — works on ALL product types
            "div.Nx9bqj",     # pre-2026 fallback
            "div._30jeq3",    # pre-2026 fallback
            "div._1vC4OE",    # pre-2026 fallback
        ]

        for selector in selectors:
            for el in soup.select(selector):
                text = el.get_text(strip=True)
                # Pure price = starts with ₹ then only digits and commas
                # Example match:   "₹1,29,999"
                # Example reject:  "Get Up to ₹500 Off"  "512 GB + 12 GB"
                if re.match(r'^₹[\d,]+$', text):
                    try:
                        price = float(text.replace("₹", "").replace(",", ""))
                        if price > 100:  # sanity check
                            return price
                    except ValueError:
                        continue

        return None

    def _extract_name(self, soup: BeautifulSoup) -> str:
        """
        Extract product name. Uses <title> tag — most reliable,
        always present, never changes format.
        """
        selectors = ["title", "span.VU-ZEz", "span.B_NuCI", "h1.yhB1nd", "h1"]

        for selector in selectors:
            el = soup.select_one(selector)
            if not el:
                continue
            name = el.get_text(strip=True)
            # Clean title tag: "Product Name - Buy ... Flipkart.com"
            if selector == "title" and " - " in name:
                name = name.split(" - ")[0].strip()
            name = re.sub(r'\s*Price in India.*$', '', name, flags=re.IGNORECASE).strip()
            if name and len(name) > 5:
                return name[:150]

        return "Unknown Product"
