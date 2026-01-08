"""
Costco Shopping Agent - Streamlit GUI

A web-based GUI for the Costco shopping automation agent.

Run with:
    streamlit run costco_app.py

Install:
    pip install streamlit playwright
    playwright install chromium
"""

import streamlit as st
import asyncio
import os
from typing import List

# Import the agent
from costco_agent import CostcoShoppingAgent, CostcoConfig

# Page config
st.set_page_config(
    page_title="Costco Shopping Agent",
    page_icon="🛒",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .status-box {
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .status-thinking { background-color: #e3f2fd; }
    .status-action { background-color: #fff3e0; }
    .status-result { background-color: #e8f5e9; }
    .status-error { background-color: #ffebee; }
    .product-card {
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "is_running" not in st.session_state:
        st.session_state.is_running = False
    if "search_results" not in st.session_state:
        st.session_state.search_results = []


def add_message(msg_type: str, content: str, data=None):
    """Add a message to the log."""
    icons = {
        "thinking": "🤔",
        "action": "⚡",
        "result": "✅",
        "error": "❌",
        "info": "ℹ️"
    }
    st.session_state.messages.append({
        "type": msg_type,
        "icon": icons.get(msg_type, "📝"),
        "content": content,
        "data": data
    })


async def run_shopping_agent(items: List[str], promo_code: str, browse_only: bool, headless: bool):
    """Run the shopping agent asynchronously."""
    st.session_state.is_running = True
    st.session_state.messages = []

    # Set headless mode
    os.environ["HEADLESS"] = str(headless).lower()

    config = CostcoConfig.from_env()

    try:
        async with CostcoShoppingAgent(config, browse_only=browse_only) as agent:
            async for message in agent.shop(
                items=items,
                promo_code=promo_code if promo_code else None,
                auto_checkout=False
            ):
                add_message(message.type, message.content, message.data)

                # Store search results
                if message.data and "products" in message.data:
                    st.session_state.search_results = message.data["products"]

    except Exception as e:
        add_message("error", f"Agent error: {str(e)}")

    st.session_state.is_running = False


def main():
    """Main Streamlit app."""
    init_session_state()

    # Header
    st.title("🛒 Costco Shopping Agent")
    st.markdown("*Automate your Costco shopping with AI*")

    # Sidebar - Configuration
    with st.sidebar:
        st.header("⚙️ Settings")

        # Mode selection
        browse_only = st.checkbox(
            "Browse Only Mode",
            value=True,
            help="Search products without logging in. Uncheck to enable full shopping."
        )

        headless = st.checkbox(
            "Headless Browser",
            value=False,
            help="Run browser invisibly in the background"
        )

        st.divider()

        # Credentials (only show if not browse_only)
        if not browse_only:
            st.subheader("🔐 Credentials")
            email = st.text_input("Costco Email", type="default")
            password = st.text_input("Costco Password", type="password")

            if email:
                os.environ["COSTCO_EMAIL"] = email
            if password:
                os.environ["COSTCO_PASSWORD"] = password

            if not email or not password:
                st.warning("Enter credentials for full shopping mode")

        st.divider()

        # Info
        st.subheader("📋 How it works")
        if browse_only:
            st.info("""
            **Browse Mode:**
            1. Enter items to search
            2. Click "Start Shopping"
            3. View real Costco results
            4. No login needed!
            """)
        else:
            st.info("""
            **Full Mode:**
            1. Enter credentials
            2. Enter items to search
            3. Click "Start Shopping"
            4. Agent adds items to cart
            5. Review before checkout
            """)

    # Main content
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📝 Shopping List")

        # Item input
        items_text = st.text_area(
            "Items to search (one per line)",
            placeholder="kirkland olive oil\ntoilet paper\npaper towels",
            height=150
        )

        # Promo code
        promo_code = st.text_input(
            "Promo Code (optional)",
            placeholder="SAVE10"
        )

        # Parse items
        items = [item.strip() for item in items_text.split("\n") if item.strip()]

        # Start button
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            start_disabled = st.session_state.is_running or not items
            if st.button("🚀 Start Shopping", disabled=start_disabled, use_container_width=True):
                # Run the agent
                asyncio.run(run_shopping_agent(items, promo_code, browse_only, headless))
                st.rerun()

        with col_btn2:
            if st.button("🗑️ Clear Log", use_container_width=True):
                st.session_state.messages = []
                st.session_state.search_results = []
                st.rerun()

        # Status indicator
        if st.session_state.is_running:
            st.info("⏳ Agent is running...")

    with col2:
        st.subheader("📊 Results")

        # Show search results
        if st.session_state.search_results:
            st.markdown("**Found Products:**")
            for i, product in enumerate(st.session_state.search_results[:5]):
                with st.container():
                    st.markdown(f"""
                    <div class="product-card">
                        <strong>{i+1}. {product.get('title', 'Unknown')[:60]}...</strong><br>
                        💰 {product.get('price', 'N/A')}
                    </div>
                    """, unsafe_allow_html=True)

    # Activity Log
    st.divider()
    st.subheader("📜 Activity Log")

    if st.session_state.messages:
        for msg in reversed(st.session_state.messages):
            msg_type = msg["type"]
            color_map = {
                "thinking": "blue",
                "action": "orange",
                "result": "green",
                "error": "red",
                "info": "gray"
            }
            color = color_map.get(msg_type, "gray")

            st.markdown(f":{color}[{msg['icon']} {msg['content']}]")

            # Show product data if available
            if msg.get("data") and "products" in msg["data"]:
                with st.expander("View products"):
                    for p in msg["data"]["products"][:5]:
                        st.write(f"• {p.get('title', 'Unknown')[:50]}... - {p.get('price', 'N/A')}")
    else:
        st.info("No activity yet. Enter items and click 'Start Shopping' to begin.")

    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; font-size: 12px;">
        Costco Shopping Agent v1.0 | Uses Playwright for browser automation
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
