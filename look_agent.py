# =============================================================
# look_agent.py  —  CLOUD-COMPATIBLE VERSION
# =============================================================
# PROBLEM: Flipkart blocks all cloud/datacenter IPs (HTTP 529)
# SOLUTION: Use RapidAPI's Flipkart API (free tier: 100 req/month)
#           Falls back to direct scraping when running locally
#
# FREE API SETUP (2 minutes):
#   1. Go to rapidapi.com → search "Flipkart"
#   2. Subscribe to "Flipkart Product Search" (free tier)
#   3. Copy your RapidAPI key
#   4. Add to .env: RAPIDAPI_KEY=your_key
#
# HOW IT WORKS:
#   Cloud: RapidAPI → Flipkart (RapidAPI has residential IPs)
#   Local: Direct requests to Flipkart (works from home IP)
# =============================================================

import re
import os
import time
import random
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


class LookAgent:
    """
    Agent 1: The LOOK Agent.

    Strategy:
      1. Try RapidAPI (works from cloud — has residential IPs)
      2. Fall back to direct requests (works from local/home IP)
    """

    def __init__(self):
        self.rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
        self.session = requests.Session()
        if self.rapidapi_key:
            logger.info("LookAgent: ready (RapidAPI mode — cloud compatible)")
        else:
            logger.info("LookAgent: ready (direct mode — works on local, may fail on cloud)")

    def fetch(self, url: str) -> dict | None:
        """Fetch product info from Flipkart URL."""
        logger.info(f"LookAgent: fetching {url[:70]}...")

        # Try RapidAPI first if key is available
        if self.rapidapi_key:
            result = self._fetch_via_rapidapi(url)
            if result:
                return result
            logger.warning("LookAgent: RapidAPI failed, trying direct...")

        # Fall back to direct request
        return self._fetch_direct(url)

    def _fetch_via_rapidapi(self, url: str) -> dict | None:
        """
        Fetch via RapidAPI Flipkart endpoints.
        Tries multiple endpoints with both ID formats.
        """
        # Flipkart has two product ID formats in URLs:
        # 1. itm_id from /p/itm7e75db4f27bd5  (starts with itm, lowercase)
        # 2. pid   from ?pid=MOBH4DQFNXH8SZ9D  (uppercase, in query params)
        itm_match = re.search(r'/p/([A-Za-z0-9]+)', url)
        pid_match  = re.search(r'[?&]pid=([A-Z0-9]+)', url)

        itm_id = itm_match.group(1) if itm_match else None
        pid_id = pid_match.group(1)  if pid_match  else None

        if not itm_id and not pid_id:
            logger.warning("LookAgent: could not extract product ID from URL")
            return None

        logger.info(f"LookAgent: itm_id={itm_id} pid={pid_id}")

        # CONFIRMED from screenshot:
        # API: Real-Time Flipkart Data (ayushsomanime)
        # Endpoint: GET "Get Single Product Data"
        # Response fields: price (int), mrp (int), title, url, highlights
        # Host will be: real-time-flipkart-data.p.rapidapi.com (without "2")
        calls = [
            # Primary: Get Single Product Data by pid
            ("https://real-time-flipkart-data.p.rapidapi.com/product",
             "real-time-flipkart-data.p.rapidapi.com",
             {"pid": pid_id or itm_id}),

            # Try with itemId format
            ("https://real-time-flipkart-data.p.rapidapi.com/product",
             "real-time-flipkart-data.p.rapidapi.com",
             {"pid": itm_id}),

            # Try with url parameter
            ("https://real-time-flipkart-data.p.rapidapi.com/product",
             "real-time-flipkart-data.p.rapidapi.com",
             {"url": url}),

            # Also try data2 variant
            ("https://real-time-flipkart-data2.p.rapidapi.com/product",
             "real-time-flipkart-data2.p.rapidapi.com",
             {"pid": pid_id or itm_id}),
        ]

        for api_url, host, params in calls:
            # Skip calls where param value is None
            if None in params.values():
                continue
            try:
                response = requests.get(
                    api_url,
                    headers={
                        "X-RapidAPI-Key": self.rapidapi_key,
                        "X-RapidAPI-Host": host,
                    },
                    params=params,
                    timeout=15,
                )
                logger.info(f"LookAgent: {host} → {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    price_str = str(
                        data.get("price") or data.get("selling_price") or
                        data.get("discounted_price") or data.get("current_price") or
                        data.get("mrp") or ""
                    )
                    price_clean = re.sub(r"[^\d.]", "", price_str)
                    name = str(
                        data.get("name") or data.get("title") or
                        data.get("product_name") or "Unknown Product"
                    )
                    if price_clean:
                        price = float(price_clean)
                        if price > 100:
                            logger.info(f"LookAgent: RapidAPI ✅ '{name[:50]}' → ₹{price:,.0f}")
                            return {"name": name[:150], "price": price, "url": url}
                    logger.warning(f"LookAgent: no price in response: {str(data)[:150]}")

                elif response.status_code == 403:
                    logger.warning(f"LookAgent: not subscribed to {host} — skipping")

            except Exception as e:
                logger.warning(f"LookAgent: {host} error: {e}")

        logger.warning("LookAgent: all RapidAPI calls failed")
        return None

    def _fetch_direct(self, url: str) -> dict | None:
        """
        Direct request to Flipkart.
        Works from home/office IP but blocked on cloud datacenter IPs.
        """
        for attempt in range(1, 4):
            ua = USER_AGENTS[(attempt - 1) % len(USER_AGENTS)]
            logger.info(f"LookAgent: direct attempt {attempt}/3")

            self.session = requests.Session()

            try:
                # Warm session with homepage
                self.session.get(
                    "https://www.flipkart.com",
                    headers=self._headers(ua),
                    timeout=15,
                )
                time.sleep(random.uniform(1.5, 3.0))

                headers = self._headers(ua)
                headers["Referer"] = "https://www.flipkart.com/"

                response = self.session.get(url, headers=headers, timeout=20)
                logger.info(f"LookAgent: HTTP {response.status_code}")

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, "lxml")
                    price = self._extract_price(soup)
                    name  = self._extract_name(soup)

                    if price:
                        logger.info(f"LookAgent: ✅ '{name[:50]}' → ₹{price:,.0f}")
                        return {"name": name, "price": price, "url": url}

                    with open("debug_flipkart.html", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    logger.warning("LookAgent: page loaded but price not found")
                    return None

                elif response.status_code in (403, 529):
                    logger.warning(f"LookAgent: blocked ({response.status_code}) attempt {attempt}")
                    time.sleep(attempt * 5)

            except Exception as e:
                logger.error(f"LookAgent: attempt {attempt} error: {e}")
                time.sleep(2)

        logger.error("LookAgent: all attempts failed — cloud IP is blocked by Flipkart")
        return None

    def _headers(self, ua: str) -> dict:
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
        }

    def _extract_price(self, soup: BeautifulSoup) -> float | None:
        selectors = ["div.v1zwn29", "div.v1zwn20", "div.Nx9bqj", "div._30jeq3"]
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
        for selector in ["title", "span.VU-ZEz", "span.B_NuCI", "h1"]:
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
