import streamlit as st
import pandas as pd
import requests
from integrate import ConnectToIntegrate, IntegrateOrders

# Read credentials and session keys from Streamlit secrets
def get_creds():
    return dict(
        api_token=st.secrets["integrate_api_token"],
        api_secret=st.secrets["integrate_api_secret"],
        uid=st.secrets.get("integrate_uid", ""),
        actid=st.secrets.get("integrate_actid", ""),
        api_session_key=st.secrets.get("integrate_api_session_key", ""),
        ws_session_key=st.secrets.get("integrate_ws_session_key", "")
    )

# Session management: handle session expiry and OTP prompt
def ensure_active_session(conn, creds):
    # Try session-based call (fast path)
    io = IntegrateOrders(conn)
    try:
        resp = io.holdings()
        if (
            isinstance(resp, dict) and
            str(resp.get("status", "")).upper() in ["FAILED", "FAIL", "ERROR"] and
            "session" in str(resp.get("message", "")).lower()
        ):
            raise Exception("Session expired")
        return io
    except Exception as e:
        st.warning("API session expired or invalid. Re-authenticating...")
        # OTP logic (if needed)
        if hasattr(conn, "login_with_otp"):
            otp = st.text_input("Enter OTP (sent to your mobile/email):", type="password")
            if st.button("Submit OTP"):
                conn.login_with_otp(creds["api_token"], creds["api_secret"], otp)
        else:
            conn.login(creds["api_token"], creds["api_secret"])
        # If your SDK requires set_session_keys, do it here
        if hasattr(conn, "set_session_keys") and creds["uid"]:
            conn.set_session_keys(creds["uid"], creds["actid"], creds["api_session_key"], creds["ws_session_key"])
        return IntegrateOrders(conn)

@st.cache_resource
def get_integrate_orders():
    creds = get_creds()
    conn = ConnectToIntegrate()
    conn.login(creds["api_token"], creds["api_secret"])
    # If your SDK requires set_session_keys, do it here
    if hasattr(conn, "set_session_keys") and creds["uid"]:
        conn.set_session_keys(creds["uid"], creds["actid"], creds["api_session_key"], creds["ws_session_key"])
    io = IntegrateOrders(conn)
    return io, conn, creds

io, conn, creds = get_integrate_orders()
io = ensure_active_session(conn, creds)

sections = [
    "📊 Holdings (Live LTP & P&L)",
    "📈 Positions",
    "🛒 Place Order",
    "📒 Order Book",
    "📗 Trade Book",
    "📘 GTT Orders",
    "📙 OCO Orders",
    "🛠️ Modify/Cancel Order",
    "🔄 Session Status"
]

st.sidebar.title("Definedge Dashboard")
section = st.sidebar.radio("Go to", sections)

if section == "📊 Holdings (Live LTP & P&L)":
    st.header("Holdings")
    try:
        data = io.holdings()
        st.write("Holdings API Response:", data)
        # Your tabular/pandas logic here
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "📈 Positions":
    st.header("Positions")
    try:
        data = io.positions()
        st.write("Positions API Response:", data)
        # Your positions table logic here
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "🛒 Place Order":
    st.header("Place Order")
    # Your order placement form logic

elif section == "📒 Order Book":
    st.header("Order Book")
    try:
        data = io.orders()
        st.write("Order Book API Response:", data)
        # Display orders
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "📗 Trade Book":
    st.header("Trade Book")
    try:
        data = io.tradebook()
        st.write("Trade Book API Response:", data)
        # Display trades
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "📘 GTT Orders":
    st.header("GTT Orders")
    # Your GTT order logic

elif section == "📙 OCO Orders":
    st.header("OCO Orders")
    # Your OCO order logic

elif section == "🛠️ Modify/Cancel Order":
    st.header("Modify/Cancel Order")
    # Your modify/cancel logic

elif section == "🔄 Session Status":
    st.header("Session Status")
    st.write("Session Keys:", creds)

# ...repeat this pattern for other codes/features...
