# =============================================================
# agents/monitor_agent.py
# =============================================================
# WHAT THIS AGENT DOES:
#   "Monitors" by comparing the new price with the old price.
#   If the price dropped below the user's target, it sends an alert.
#
# THINK OF IT LIKE:
#   A person who watches a price tag and says
#   "Hey! It went down! You wanted it under ₹50,000 — it's ₹45,000 now!"
#
# WHY IT'S CALLED "MONITOR AGENT":
#   In multi-agent systems, the Monitor agent WATCHES for changes
#   and DECIDES if action is needed.
# =============================================================

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)


class MonitorAgent:
    """
    Agent 2: The MONITOR Agent.

    Responsibility:
      1. Compare new price with the previous price
      2. Check if price dropped below the user's target
      3. Send email alert if target is reached

    This agent makes DECISIONS. It doesn't scrape or store —
    it just checks conditions and acts on them.
    """

    def __init__(self, smtp_host: str = "", smtp_user: str = "", smtp_pass: str = ""):
        """
        Args:
            smtp_host: Email server (e.g. "smtp.gmail.com")
            smtp_user: Your Gmail address
            smtp_pass: Gmail App Password (not your regular password!)
        """
        self.smtp_host = smtp_host
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.email_enabled = bool(smtp_host and smtp_user and smtp_pass)

        if self.email_enabled:
            logger.info("MonitorAgent: email alerts ENABLED")
        else:
            logger.info("MonitorAgent: email alerts DISABLED (no SMTP config)")

    def check(
        self,
        product_name: str,
        current_price: float,
        previous_price: float | None,
        target_price: float | None,
        alert_email: str = "",
    ) -> dict:
        """
        Compare prices and decide if an alert is needed.

        Args:
            product_name:   Name of the product
            current_price:  Price we just scraped
            previous_price: Last recorded price (None if first time)
            target_price:   User's desired price threshold
            alert_email:    Email to send alert to

        Returns:
            dict with keys:
              - price_dropped (bool): Did price go down?
              - drop_amount (float): How much it dropped (₹)
              - drop_percent (float): Drop as percentage
              - target_reached (bool): Is price now below target?
              - alert_sent (bool): Was email sent?
        """
        result = {
            "price_dropped": False,
            "drop_amount": 0.0,
            "drop_percent": 0.0,
            "target_reached": False,
            "alert_sent": False,
        }

        # ── Step 1: Check if price dropped ─────────────────────────
        if previous_price is not None and current_price < previous_price:
            drop = previous_price - current_price
            drop_pct = (drop / previous_price) * 100

            result["price_dropped"] = True
            result["drop_amount"] = round(drop, 2)
            result["drop_percent"] = round(drop_pct, 2)

            logger.info(
                f"MonitorAgent: price dropped ₹{drop:,.0f} "
                f"({drop_pct:.1f}%) for {product_name[:40]}"
            )
        else:
            logger.info(f"MonitorAgent: no price drop detected for {product_name[:40]}")

        # ── Step 2: Check if target price is reached ────────────────
        if target_price and current_price <= target_price:
            result["target_reached"] = True
            logger.info(
                f"MonitorAgent: TARGET REACHED! "
                f"₹{current_price:,.0f} ≤ ₹{target_price:,.0f}"
            )

        # ── Step 3: Send alert if needed ────────────────────────────
        should_alert = (
            result["target_reached"]  # Always alert on target
            or (result["price_dropped"] and result["drop_percent"] >= 5)  # Alert on 5%+ drop
        )

        if should_alert and alert_email and self.email_enabled:
            sent = self._send_email(
                to_email=alert_email,
                product_name=product_name,
                current_price=current_price,
                previous_price=previous_price,
                target_price=target_price,
                drop_amount=result["drop_amount"],
                drop_percent=result["drop_percent"],
                target_reached=result["target_reached"],
            )
            result["alert_sent"] = sent

        elif should_alert and not self.email_enabled:
            logger.info("MonitorAgent: alert triggered but email not configured")

        return result

    def _send_email(
        self,
        to_email: str,
        product_name: str,
        current_price: float,
        previous_price: float | None,
        target_price: float | None,
        drop_amount: float,
        drop_percent: float,
        target_reached: bool,
    ) -> bool:
        """
        Sends an HTML email alert.

        HOW TO ENABLE EMAIL:
          1. Go to Google Account → Security → App Passwords
          2. Create an App Password for "Mail"
          3. Add to your .env file:
             SMTP_HOST=smtp.gmail.com
             SMTP_USER=your@gmail.com
             SMTP_PASS=your_app_password

        Returns True if email was sent successfully.
        """
        try:
            # Build the email subject
            if target_reached:
                subject = f"🎯 Price Target Reached! {product_name[:50]}"
            else:
                subject = f"📉 Price Dropped {drop_percent:.0f}%! {product_name[:50]}"

            # Build a clean HTML email body
            html_body = f"""
            <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
                <h2 style="color: #2d6a4f;">Price Alert!</h2>
                <h3 style="color: #333;">{product_name}</h3>
                <table style="width:100%; border-collapse:collapse;">
                    <tr>
                        <td style="padding:8px; color:#666;">Current Price</td>
                        <td style="padding:8px; font-size:24px; color:#e63946; font-weight:bold;">
                            ₹{current_price:,.0f}
                        </td>
                    </tr>
                    {"<tr><td style='padding:8px;color:#666;'>Previous Price</td><td style='padding:8px;'>₹" + f"{previous_price:,.0f}</td></tr>" if previous_price else ""}
                    {"<tr><td style='padding:8px;color:#666;'>Price Drop</td><td style='padding:8px; color:#2d6a4f;'>₹" + f"{drop_amount:,.0f} ({drop_percent:.1f}%)</td></tr>" if drop_amount else ""}
                    {"<tr><td style='padding:8px;color:#666;'>Your Target</td><td style='padding:8px;'>₹" + f"{target_price:,.0f}</td></tr>" if target_price else ""}
                </table>
                {"<p style='color:#2d6a4f; font-weight:bold;'>✅ Your price target has been reached!</p>" if target_reached else ""}
                <p style="color:#999; font-size:12px;">
                    Alert sent at {datetime.now().strftime('%Y-%m-%d %H:%M')} by PriceTracker
                </p>
            </div>
            </body></html>
            """

            # Create the email message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = to_email
            msg.attach(MIMEText(html_body, "html"))

            # Send via Gmail SMTP
            with smtplib.SMTP(self.smtp_host, 587) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, to_email, msg.as_string())

            logger.info(f"MonitorAgent: alert email sent to {to_email}")
            return True

        except Exception as e:
            logger.error(f"MonitorAgent: email failed: {e}")
            return False
