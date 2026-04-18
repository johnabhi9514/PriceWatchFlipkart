# =============================================================
# agents/store_agent.py
# =============================================================
# WHAT THIS AGENT DOES:
#   "Stores" all price data in a SQLite database.
#   Also handles reading data back for charts and display.
#
# THINK OF IT LIKE:
#   A record-keeper who writes down every price check
#   in a logbook, and can look up any product's history.
#
# WHY SQLITE:
#   - Zero setup — it's just a single .db file
#   - Built into Python — no installation needed
#   - Works free on Render + Supabase for persistence
#   - Perfect for small to medium projects
#
# DATABASE STRUCTURE:
#   Table: products
#     - id, url, name, target_price, alert_email, created_at
#
#   Table: price_history
#     - id, product_id, price, checked_at, alert_sent
# =============================================================

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class StoreAgent:
    """
    Agent 3: The STORE Agent.

    Responsibility:
      - Save products that users want to track
      - Record price every time LookAgent checks it
      - Read back history for charts and display

    This agent only talks to the database.
    It doesn't scrape or make decisions.
    """

    def __init__(self, db_path: str = "prices.db"):
        """
        Args:
            db_path: Path to the SQLite database file.
                     On Render free tier, use "/tmp/prices.db"
                     because the regular filesystem resets on restart.
                     For Supabase, we'd use PostgreSQL instead.
        """
        self.db_path = db_path
        self._create_tables()
        logger.info(f"StoreAgent: database ready at {db_path}")

    @contextmanager
    def _get_conn(self):
        """
        Helper that opens and closes database connection safely.

        Using a context manager (the 'with' keyword) ensures
        the connection always closes, even if an error occurs.
        This prevents database corruption.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Makes rows behave like dicts
        try:
            yield conn
            conn.commit()  # Save changes
        except Exception as e:
            conn.rollback()  # Undo changes if error
            raise e
        finally:
            conn.close()

    def _create_tables(self):
        """
        Creates database tables if they don't exist yet.

        This runs every time the app starts. The "IF NOT EXISTS"
        clause means it's safe to run multiple times.
        """
        with self._get_conn() as conn:
            conn.executescript("""
                -- Table 1: Products the user wants to track
                CREATE TABLE IF NOT EXISTS products (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    url          TEXT NOT NULL UNIQUE,
                    name         TEXT NOT NULL,
                    target_price REAL,
                    alert_email  TEXT,
                    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Table 2: Price records over time (one row per check)
                CREATE TABLE IF NOT EXISTS price_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id  INTEGER NOT NULL,
                    price       REAL NOT NULL,
                    checked_at  TEXT DEFAULT CURRENT_TIMESTAMP,
                    alert_sent  INTEGER DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                );
            """)
        logger.info("StoreAgent: tables ready")

    # ── PRODUCT OPERATIONS ─────────────────────────────────────────────

    def add_product(
        self,
        url: str,
        name: str,
        target_price: float | None = None,
        alert_email: str = "",
    ) -> int:
        """
        Add a new product to track.

        Returns the product's ID in the database.
        If the product already exists (same URL), updates it.
        """
        with self._get_conn() as conn:
            # INSERT OR REPLACE: if URL already exists, update it
            cursor = conn.execute(
                """
                INSERT INTO products (url, name, target_price, alert_email)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    name         = excluded.name,
                    target_price = excluded.target_price,
                    alert_email  = excluded.alert_email
                """,
                (url, name, target_price, alert_email),
            )
            product_id = cursor.lastrowid
            logger.info(f"StoreAgent: saved product '{name}' (id={product_id})")
            return product_id

    def get_all_products(self) -> list[dict]:
        """Returns all tracked products as a list of dicts."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM products ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def get_product(self, product_id: int) -> dict | None:
        """Returns one product by ID, or None if not found."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete_product(self, product_id: int):
        """Delete a product and all its price history."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
            conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
            logger.info(f"StoreAgent: deleted product id={product_id}")

    # ── PRICE HISTORY OPERATIONS ───────────────────────────────────────

    def save_price(
        self,
        product_id: int,
        price: float,
        alert_sent: bool = False,
    ) -> int:
        """
        Save a price check to history.

        Args:
            product_id: Which product this price is for
            price:      The price we found
            alert_sent: Whether we sent an email alert for this check

        Returns the new price record's ID.
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO price_history (product_id, price, alert_sent)
                VALUES (?, ?, ?)
                """,
                (product_id, price, 1 if alert_sent else 0),
            )
            logger.info(
                f"StoreAgent: saved price ₹{price:,.0f} for product id={product_id}"
            )
            return cursor.lastrowid

    def get_price_history(self, product_id: int, days: int = 30) -> list[dict]:
        """
        Get price history for a product.

        Args:
            product_id: Which product to get history for
            days:       How many days back to look (default: 30)

        Returns list of dicts like:
            [{"price": 49999, "checked_at": "2025-01-01 12:00:00"}, ...]
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT price, checked_at, alert_sent
                FROM price_history
                WHERE product_id = ?
                  AND checked_at >= datetime('now', ?)
                ORDER BY checked_at ASC
                """,
                (product_id, f"-{days} days"),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_latest_price(self, product_id: int) -> float | None:
        """
        Get the most recently recorded price for a product.
        Returns None if no price has been recorded yet.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT price FROM price_history
                WHERE product_id = ?
                ORDER BY checked_at DESC
                LIMIT 1
                """,
                (product_id,),
            ).fetchone()
            return row["price"] if row else None

    def get_stats(self, product_id: int) -> dict:
        """
        Get summary statistics for a product.

        Returns dict with: current, lowest, highest, avg price,
        total checks, and first check date.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)          AS total_checks,
                    MIN(price)        AS lowest_price,
                    MAX(price)        AS highest_price,
                    AVG(price)        AS avg_price,
                    MIN(checked_at)   AS first_check,
                    MAX(checked_at)   AS last_check
                FROM price_history
                WHERE product_id = ?
                """,
                (product_id,),
            ).fetchone()

            if not row or row["total_checks"] == 0:
                return {}

            latest = self.get_latest_price(product_id)

            return {
                "current_price":  latest,
                "lowest_price":   row["lowest_price"],
                "highest_price":  row["highest_price"],
                "avg_price":      round(row["avg_price"], 2),
                "total_checks":   row["total_checks"],
                "first_check":    row["first_check"],
                "last_check":     row["last_check"],
            }
