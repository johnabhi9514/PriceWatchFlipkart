# =============================================================
# app.py  —  Streamlit UI
# =============================================================
# HOW TO RUN:
#   pip install -r requirements.txt
#   streamlit run app.py
#
# HOW TO DEPLOY FREE (Render):
#   See DEPLOY.md
# =============================================================

import streamlit as st
import pandas as pd
import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

# Our agents
from orchestrator import PriceTrackerOrchestrator

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Price Tracker",
    page_icon="📉",
    layout="wide",
)

# ── Initialize orchestrator (cached so it's created only once) ─────────────────
@st.cache_resource
def get_orchestrator():
    return PriceTrackerOrchestrator()

@st.cache_resource
def get_scheduler():
    """
    Creates a background scheduler that checks prices every 24 hours.

    @st.cache_resource means this runs only ONCE when the app starts,
    not on every page refresh.
    """
    orc = get_orchestrator()
    scheduler = BackgroundScheduler()

    # Run all price checks every 24 hours
    scheduler.add_job(
        func     = orc.run_all_checks,
        trigger  = "interval",
        hours    = 24,
        id       = "daily_check",
        name     = "Daily price check",
        replace_existing = True,
    )

    scheduler.start()
    return scheduler

# Initialize both
orc       = get_orchestrator()
scheduler = get_scheduler()

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📉 Smart Price Tracker")
st.caption("Multi-agent system: Look → Monitor → Store. Tracks Flipkart prices daily.")

# Show scheduler status
next_run = scheduler.get_job("daily_check")
if next_run and next_run.next_run_time:
    st.info(
        f"⏰ Next automatic check: "
        f"{next_run.next_run_time.strftime('%Y-%m-%d %H:%M')}",
        icon="🤖",
    )

st.divider()

# ── Sidebar: Add new product ───────────────────────────────────────────────────
with st.sidebar:
    st.header("➕ Track a Product")
    st.caption("Paste any Flipkart product URL")

    url_input = st.text_area(
        "Flipkart Product URL",
        placeholder="https://www.flipkart.com/...",
        height=100,
    )

    target_price = st.number_input(
        "Alert me when price drops below (₹)",
        min_value=0,
        value=0,
        step=100,
        help="Set 0 to disable price target alerts",
    )

    alert_email = st.text_input(
        "Alert email (optional)",
        placeholder="you@gmail.com",
        help="Get email when price reaches your target",
    )

    if st.button("🔍 Start Tracking", type="primary", use_container_width=True):
        if not url_input.strip():
            st.error("Please enter a Flipkart URL")
        elif "flipkart.com" not in url_input:
            st.error("Please enter a Flipkart URL (must contain flipkart.com)")
        else:
            with st.spinner("Look agent is fetching price..."):
                result = orc.add_product(
                    url          = url_input.strip(),
                    target_price = float(target_price) if target_price > 0 else None,
                    alert_email  = alert_email.strip(),
                )

            if result["success"]:
                st.success(
                    f"✅ Added!\n\n"
                    f"**{result['product_name'][:60]}**\n\n"
                    f"Current price: ₹{result['current_price']:,.0f}"
                )
                st.rerun()
            else:
                st.error(f"❌ {result.get('error', 'Failed to add product')}")

    st.divider()
    st.caption("**How it works:**")
    st.caption("🔍 **Look** — scrapes Flipkart price")
    st.caption("📊 **Monitor** — detects price drops")
    st.caption("💾 **Store** — saves history to SQLite")
    st.caption("⏰ Auto-checks every 24 hours")

# ── Main dashboard ─────────────────────────────────────────────────────────────
products = orc.store.get_all_products()

if not products:
    # Empty state
    st.markdown("""
    <div style="text-align:center; padding:60px 20px; color:#888;">
        <h2>No products tracked yet</h2>
        <p>Paste a Flipkart product URL in the sidebar to get started.</p>
        <p><strong>Example:</strong><br>
        https://www.flipkart.com/apple-iphone-15/p/itm...</p>
    </div>
    """, unsafe_allow_html=True)

else:
    # ── Top-level metrics ──────────────────────────────────────────
    total_products = len(products)
    stats_list = [orc.store.get_stats(p["id"]) for p in products]

    # Count how many products have dropped prices
    dropped_count = sum(
        1 for s in stats_list
        if s.get("current_price") and s.get("lowest_price")
        and s["current_price"] <= s["lowest_price"]
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Products Tracked", total_products)
    col2.metric("At Lowest Price", dropped_count)
    col3.metric(
        "Last Checked",
        stats_list[0].get("last_check", "Never")[:10] if stats_list else "Never",
    )

    st.divider()

    # ── Manual refresh button ──────────────────────────────────────
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("🔄 Check All Now", use_container_width=True):
            with st.spinner("All agents running..."):
                results = orc.run_all_checks()
            drops = sum(1 for r in results if r.get("price_dropped"))
            st.success(
                f"✅ Checked {len(results)} products. "
                f"{drops} price drops found."
            )
            st.rerun()

    st.divider()

    # ── Product cards ──────────────────────────────────────────────
    for product in products:
        stats = orc.store.get_stats(product["id"])
        history = orc.store.get_price_history(product["id"], days=30)

        current  = stats.get("current_price")
        lowest   = stats.get("lowest_price")
        highest  = stats.get("highest_price")
        target   = product.get("target_price")

        # Determine badge
        if current and lowest and current == lowest:
            badge = "🟢 Lowest ever!"
        elif target and current and current <= target:
            badge = "🎯 Target reached!"
        else:
            badge = ""

        # Build expander title safely (avoid nested f-string issues)
        price_str = f"₹{current:,.0f}" if current else "No price yet"
        expander_title = f"**{product['name'][:70]}**   {price_str}   {badge}"

        with st.expander(expander_title, expanded=True):
            col_left, col_right = st.columns([2, 3])

            with col_left:
                # Price stats
                st.markdown("**Price Summary**")

                m1, m2 = st.columns(2)
                m1.metric("Current", f"₹{current:,.0f}" if current else "—")
                m2.metric("Lowest", f"₹{lowest:,.0f}" if lowest else "—")

                m3, m4 = st.columns(2)
                m3.metric("Highest", f"₹{highest:,.0f}" if highest else "—")
                m4.metric(
                    "Avg",
                    f"₹{stats.get('avg_price', 0):,.0f}"
                    if stats.get("avg_price") else "—",
                )

                if target:
                    st.caption(f"🎯 Your target: ₹{target:,.0f}")
                    if current:
                        diff = current - target
                        if diff <= 0:
                            st.success("✅ Target price reached!")
                        else:
                            st.caption(f"₹{diff:,.0f} away from target")

                st.caption(
                    f"Tracking since: {product.get('created_at', '')[:10]}"
                )
                st.caption(f"Total checks: {stats.get('total_checks', 0)}")

                # Action buttons
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if st.button(
                        "🔄 Check now",
                        key=f"check_{product['id']}",
                        use_container_width=True,
                    ):
                        with st.spinner("Look agent checking..."):
                            result = orc.run_check(product["id"])
                        if result["success"]:
                            price_str = f"₹{result['current_price']:,.0f}"
                            if result["price_dropped"]:
                                st.success(
                                    f"Price dropped! {price_str} "
                                    f"(↓₹{result['drop_amount']:,.0f})"
                                )
                            else:
                                st.info(f"No change: {price_str}")
                            st.rerun()
                        else:
                            st.error(result.get("error", "Check failed"))

                with btn_col2:
                    if st.button(
                        "🗑️ Remove",
                        key=f"del_{product['id']}",
                        use_container_width=True,
                    ):
                        orc.store.delete_product(product["id"])
                        st.rerun()

            with col_right:
                # Price history chart
                if history:
                    df = pd.DataFrame(history)
                    df["checked_at"] = pd.to_datetime(df["checked_at"])
                    df = df.rename(columns={"checked_at": "Date", "price": "Price (₹)"})

                    st.markdown("**Price History (last 30 days)**")
                    st.line_chart(
                        df.set_index("Date")["Price (₹)"],
                        use_container_width=True,
                        height=220,
                        color="#2d6a4f",
                    )

                    # Show target line info
                    if target:
                        st.caption(f"Target: ₹{target:,.0f}")
                else:
                    st.caption("No price history yet. Check again tomorrow!")

            # Link to product
            st.markdown(
                f"[🔗 View on Flipkart]({product['url']})",
                unsafe_allow_html=False,
            )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Built with Python · Streamlit · SQLite · APScheduler  "
    "| Multi-Agent System: Look → Monitor → Store"
)
