# =============================================================
# look_agent.py  —  FINAL VERSION (requests-based)
# =============================================================
# WHY SWITCHED FROM PLAYWRIGHT TO REQUESTS:
#   Playwright needs a Chrome binary (~200MB) downloaded at runtime.
#   Free cloud hosts (Streamlit Cloud, Render) don't allow this.
#   requests works everywhere with zero setup.
#
# HOW WE BYPASS FLIPKART 403:
#   1. Use a real session (persists cookies between requests)
#   2. Visit homepage first to get session cookies
#   3. Send full browser headers on every request
#   4. Retry with different User-Agents if blocked
#
# TESTED ON: Samsung S25 Ultra, iPhone 16, PlayStation 5,
#            Ustraa Beard Oil, Kalapushpi Saree (April 2026)
# =============================================================

import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Rotate between multiple real User-Agent strings
# If one gets blocked, the next retry uses a different one
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def get_headers(user_agent: str = None) -> dict:
    """Returns full browser headers."""
    ua = user_agent or random.choice(USER_AGENTS)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1",
    }


class LookAgent:
    """
    Agent 1: The LOOK Agent.
    Uses requests + session to fetch Flipkart prices.
    Works on all cloud platforms — no browser binary needed.
    """

    def __init__(self):
        self.session = requests.Session()
        logger.info("LookAgent: ready (requests mode)")

    def _warm_session(self, user_agent: str):
        """Visit Flipkart homepage to get session cookies."""
        try:
            self.session.get(
                "https://www.flipkart.com",
                headers=get_headers(user_agent),
                timeout=15,
                allow_redirects=True,
            )
            time.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            logger.debug(f"Session warm failed (non-critical): {e}")

    def fetch(self, url: str) -> dict | None:
        """
        Fetch Flipkart product URL and extract price + name.

        Tries up to 3 times with different User-Agents.
        Each attempt warms the session first (gets cookies).
        """
        logger.info(f"LookAgent: fetching {url[:70]}...")

        for attempt in range(1, 4):
            ua = USER_AGENTS[(attempt - 1) % len(USER_AGENTS)]
            logger.info(f"LookAgent: attempt {attempt}/3")

            # Fresh session each attempt
            self.session = requests.Session()
            self._warm_session(ua)

            try:
                headers = get_headers(ua)
                headers["Referer"] = "https://www.flipkart.com/"

                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=20,
                    allow_redirects=True,
                )

                logger.info(f"LookAgent: HTTP {response.status_code}")

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "lxml")
                    price = self._extract_price(soup)
                    name  = self._extract_name(soup)

                    if price:
                        logger.info(f"LookAgent: ✅ '{name[:50]}' → ₹{price:,.0f}")
                        return {"name": name, "price": price, "url": url}

                    # Price not found — save debug file
                    with open("debug_flipkart.html", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    logger.warning("LookAgent: page loaded but price not found")

                elif response.status_code == 403:
                    logger.warning(f"LookAgent: 403 blocked on attempt {attempt}")
                    time.sleep(attempt * 4)

            except Exception as e:
                logger.error(f"LookAgent: error on attempt {attempt}: {e}")
                time.sleep(2)

        logger.error("LookAgent: all attempts failed")
        return None

    def _extract_price(self, soup: BeautifulSoup) -> float | None:
        """
        Extract selling price. Confirmed classes (April 2026):
          v1zwn29 = discounted selling price (electronics/mobiles)
          v1zwn20 = universal price (all product types)
        """
        selectors = [
            "div.v1zwn29",
            "div.v1zwn20",
            "div.Nx9bqj",
            "div._30jeq3",
            "div._1vC4OE",
        ]
        for selector in selectors:
            for el in soup.select(selector):
                text = el.get_text(strip=True)
                if re.match(r'^₹[\d,]+$', text):
                    try:
                        price = float(text.replace("₹", "").replace(",", ""))
                        if price > 100:
                            return price
                    except ValueError:
                        continue
        return None

    def _extract_name(self, soup: BeautifulSoup) -> str:
        """Extract product name from title tag."""
        selectors = ["title", "span.VU-ZEz", "span.B_NuCI", "h1.yhB1nd", "h1"]
        for selector in selectors:
            el = soup.select_one(selector)
            if not el:
                continue
            name = el.get_text(strip=True)
            if selector == "title" and " - " in name:
                name = name.split(" - ")[0].strip()
            name = re.sub(r'\s*Price in India.*$', '', name, flags=re.IGNORECASE).strip()
            if name and len(name) > 5:
                return name[:150]
        return "Unknown Product"
