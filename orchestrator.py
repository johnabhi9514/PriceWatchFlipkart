# =============================================================
# orchestrator.py
# =============================================================
# WHAT THE ORCHESTRATOR DOES:
#   Coordinates all three agents to work together.
#   Runs on a schedule (every 24 hours) automatically.
#
# THINK OF IT LIKE:
#   A manager who tells each team member what to do and in what order:
#   1. "Look Agent — go check the price"
#   2. "Monitor Agent — compare it with what we had before"
#   3. "Store Agent — write it down"
#
# THE FLOW:
#   LookAgent.fetch(url)
#       → gets current price
#   MonitorAgent.check(new_price, old_price, target)
#       → decides if alert needed
#   StoreAgent.save_price(product_id, price, alert_sent)
#       → saves to database
# =============================================================

import logging
import os
from datetime import datetime

from look_agent import LookAgent
from monitor_agent import MonitorAgent
from store_agent import StoreAgent

logger = logging.getLogger(__name__)


class PriceTrackerOrchestrator:
    """
    The Orchestrator coordinates all three agents.

    It's the only class that knows about all three agents.
    Each agent only does its own job — the orchestrator
    makes them work as a team.
    """

    def __init__(self):
        # Determine database path
        # On Render free tier, /tmp persists during the session
        # For production use Supabase (free PostgreSQL)
        db_path = os.getenv("DB_PATH", "prices.db")

        # Create all three agents
        self.look    = LookAgent()
        self.monitor = MonitorAgent(
            smtp_host = os.getenv("SMTP_HOST", ""),
            smtp_user = os.getenv("SMTP_USER", ""),
            smtp_pass = os.getenv("SMTP_PASS", ""),
        )
        self.store   = StoreAgent(db_path=db_path)

        logger.info("Orchestrator: all agents initialized")

    def run_check(self, product_id: int) -> dict:
        """
        Run one full price check cycle for a single product.

        This is the main workflow — it calls all three agents in order.

        Args:
            product_id: The database ID of the product to check

        Returns:
            A dict with the result of this check:
            {
                "success": True/False,
                "product_name": "...",
                "current_price": 49999.0,
                "previous_price": 52000.0,
                "price_dropped": True,
                "drop_amount": 2001.0,
                "alert_sent": False,
                "error": None
            }
        """
        result = {
            "success": False,
            "product_name": "",
            "current_price": None,
            "previous_price": None,
            "price_dropped": False,
            "drop_amount": 0,
            "drop_percent": 0,
            "target_reached": False,
            "alert_sent": False,
            "error": None,
            "checked_at": datetime.now().isoformat(),
        }

        try:
            # ── Step 1: Get product from database ───────────────────
            product = self.store.get_product(product_id)
            if not product:
                result["error"] = f"Product {product_id} not found"
                return result

            result["product_name"] = product["name"]

            # ── Step 2: LOOK — fetch current price ──────────────────
            logger.info(f"Orchestrator: running check for '{product['name'][:40]}'")
            fetched = self.look.fetch(product["url"])

            if fetched is None:
                result["error"] = "LookAgent could not fetch price"
                return result

            current_price = fetched["price"]
            result["current_price"] = current_price

            # Update product name if Flipkart returned a better one
            if fetched["name"] != "Unknown Product":
                product["name"] = fetched["name"]
                result["product_name"] = fetched["name"]

            # ── Step 3: MONITOR — compare and decide ─────────────────
            previous_price = self.store.get_latest_price(product_id)
            result["previous_price"] = previous_price

            monitor_result = self.monitor.check(
                product_name   = product["name"],
                current_price  = current_price,
                previous_price = previous_price,
                target_price   = product.get("target_price"),
                alert_email    = product.get("alert_email", ""),
            )

            result["price_dropped"]   = monitor_result["price_dropped"]
            result["drop_amount"]     = monitor_result["drop_amount"]
            result["drop_percent"]    = monitor_result["drop_percent"]
            result["target_reached"]  = monitor_result["target_reached"]
            result["alert_sent"]      = monitor_result["alert_sent"]

            # ── Step 4: STORE — save price to database ───────────────
            self.store.save_price(
                product_id = product_id,
                price      = current_price,
                alert_sent = monitor_result["alert_sent"],
            )

            result["success"] = True
            logger.info(
                f"Orchestrator: check complete — ₹{current_price:,.0f} "
                f"{'↓ dropped' if monitor_result['price_dropped'] else '→ no change'}"
            )

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Orchestrator: check failed: {e}")

        return result

    def run_all_checks(self) -> list[dict]:
        """
        Run price checks for ALL tracked products.

        This is what the scheduler calls every 24 hours.
        Returns a list of results, one per product.
        """
        products = self.store.get_all_products()

        if not products:
            logger.info("Orchestrator: no products to check")
            return []

        logger.info(f"Orchestrator: checking {len(products)} products...")
        results = []

        for product in products:
            result = self.run_check(product["id"])
            results.append(result)

        successful = sum(1 for r in results if r["success"])
        logger.info(
            f"Orchestrator: batch complete — "
            f"{successful}/{len(products)} successful"
        )

        return results

    def add_product(
        self,
        url: str,
        target_price: float | None = None,
        alert_email: str = "",
    ) -> dict:
        """
        Add a new product and immediately fetch its first price.

        This combines StoreAgent (to save the product) and
        LookAgent (to get the initial price right away).

        Returns the result dict from run_check.
        """
        # Immediately fetch the product name and price
        fetched = self.look.fetch(url)

        if fetched is None:
            return {
                "success": False,
                "error": "Could not fetch product. Check the URL and try again.",
            }

        # Save the product to database
        product_id = self.store.add_product(
            url          = url,
            name         = fetched["name"],
            target_price = target_price,
            alert_email  = alert_email,
        )

        # Save the first price reading
        self.store.save_price(
            product_id = product_id,
            price      = fetched["price"],
        )

        logger.info(
            f"Orchestrator: added '{fetched['name'][:40]}' "
            f"at ₹{fetched['price']:,.0f}"
        )

        return {
            "success": True,
            "product_id": product_id,
            "product_name": fetched["name"],
            "current_price": fetched["price"],
        }
