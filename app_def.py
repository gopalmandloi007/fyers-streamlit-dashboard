import streamlit as st
import pandas as pd
from integrate import ConnectToIntegrate, IntegrateOrders

# Read secrets (TOML) from .streamlit/secrets.toml
api_token = st.secrets["integrate_api_token"]
api_secret = st.secrets["integrate_api_secret"]
uid = st.secrets.get("integrate_uid", "")
actid = st.secrets.get("integrate_actid", "")
api_session_key = st.secrets.get("integrate_api_session_key", "")
ws_session_key = st.secrets.get("integrate_ws_session_key", "")

# Session management
@st.cache_resource
def get_io():
    conn = ConnectToIntegrate()
    conn.login(api_token, api_secret)
    io = IntegrateOrders(conn)
    return io, conn

io, conn = get_io()

def ensure_active_session(io, conn):
    try:
        resp = io.holdings()
        if (
            isinstance(resp, dict)
            and str(resp.get("status", "")).upper() in ["FAILED", "FAIL", "ERROR"]
            and "session" in str(resp.get("message", "")).lower()
        ):
            st.warning("Session expired. Please regenerate or refresh session keys.")
            st.stop()
        return io
    except Exception as e:
        st.error(f"Session error: {e}")
        st.stop()

io = ensure_active_session(io, conn)

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
    st.header("Holdings (Live LTP & P&L)")
    try:
        data = io.holdings()
        st.write("Holdings API Response:", data)
        if data.get("data"):
            df = pd.DataFrame(data["data"])
            st.dataframe(df)
        else:
            st.info(data.get("message", "No holdings found."))
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "📈 Positions":
    st.header("Positions")
    try:
        data = io.positions()
        st.write("Positions API Response:", data)
        if data.get("positions"):
            df = pd.DataFrame(data["positions"])
            st.dataframe(df)
        else:
            st.info(data.get("message", "No positions found."))
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "🛒 Place Order":
    st.header("Place Order")
    with st.form("order_form"):
        symbol = st.text_input("Symbol (e.g. SBIN-EQ)")
        qty = st.number_input("Quantity", min_value=1)
        price = st.number_input("Price (0 = Market)", min_value=0.0, value=0.0)
        side = st.selectbox("Side", ["BUY", "SELL"])
        product = st.selectbox("Product", ["CNC", "MIS"])
        price_type = st.selectbox("Order Type", ["LIMIT", "MARKET"])
        submit = st.form_submit_button("Place Order")
        if submit and symbol:
            try:
                resp = io.place_order(
                    tradingsymbol=symbol,
                    exchange="NSE",
                    order_type=side,
                    quantity=int(qty),
                    product_type=product,
                    price_type=price_type,
                    price=str(price)
                )
                st.success(f"Order placed! Response: {resp}")
            except Exception as e:
                st.error(f"Order failed: {e}")

elif section == "📒 Order Book":
    st.header("Order Book")
    try:
        data = io.orders()
        st.write("Order Book API Response:", data)
        if data.get("orders"):
            df = pd.DataFrame(data["orders"])
            st.dataframe(df)
        else:
            st.info(data.get("message", "No orders found."))
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "📗 Trade Book":
    st.header("Trade Book")
    try:
        data = io.tradebook()
        st.write("Trade Book API Response:", data)
        if data.get("trades"):
            df = pd.DataFrame(data["trades"])
            st.dataframe(df)
        else:
            st.info(data.get("message", "No trades found."))
    except Exception as e:
        st.error(f"Error: {e}")

elif section == "📘 GTT Orders":
    st.header("GTT Orders (Place)")
    symbol = st.text_input("Symbol for GTT", key="gtt_symbol")
    qty = st.number_input("Quantity", min_value=1, key="gtt_qty")
    trigger_price = st.number_input("Trigger Price", key="gtt_trigger")
    price = st.number_input("Order Price", key="gtt_price")
    side = st.selectbox("Side", ["BUY", "SELL"], key="gtt_side")
    if st.button("Place GTT Order"):
        try:
            resp = io.place_gtt_order(
                tradingsymbol=symbol,
                exchange="NSE",
                order_type=side,
                quantity=str(qty),
                alert_price=str(trigger_price),
                price=str(price),
                condition="LTP_BELOW" if side=="SELL" else "LTP_ABOVE"
            )
            st.success(f"GTT Order Response: {resp}")
        except Exception as e:
            st.error(f"GTT order failed: {e}")

elif section == "📙 OCO Orders":
    st.header("OCO Orders (Place)")
    symbol = st.text_input("Symbol for OCO", key="oco_symbol")
    target_qty = st.number_input("Target Quantity", min_value=1, key="oco_tqty")
    stoploss_qty = st.number_input("Stoploss Quantity", min_value=1, key="oco_sqty")
    target_price = st.number_input("Target Price", key="oco_tprice")
    stoploss_price = st.number_input("Stoploss Price", key="oco_sprice")
    side = st.selectbox("Side", ["BUY", "SELL"], key="oco_side")
    if st.button("Place OCO Order"):
        try:
            resp = io.place_oco_order(
                tradingsymbol=symbol,
                exchange="NSE",
                order_type=side,
                target_quantity=str(target_qty),
                stoploss_quantity=str(stoploss_qty),
                target_price=str(target_price),
                stoploss_price=str(stoploss_price),
                remarks="OCO GTT via Streamlit"
            )
            st.success(f"OCO Order Response: {resp}")
        except Exception as e:
            st.error(f"OCO order failed: {e}")

elif section == "🛠️ Modify/Cancel Order":
    st.header("Modify/Cancel Pending Orders")
    try:
        data = io.orders()
        st.write("Orders API Response:", data)
        order_book = data.get("orders", [])
        pending = [o for o in order_book if o.get("order_status") in ("NEW", "OPEN", "REPLACED") and int(float(o.get("pending_qty", 0))) > 0]
        if not pending:
            st.info("No pending orders.")
        else:
            df = pd.DataFrame(pending)
            st.dataframe(df)
            order_id = st.selectbox("Select order_id to modify/cancel:", df["order_id"])
            action = st.radio("Action", ["Modify", "Cancel"])
            if action == "Cancel" and st.button("Cancel Order"):
                try:
                    resp = io.cancel_order(order_id)
                    st.success(f"Cancelled order {order_id}: {resp}")
                except Exception as e:
                    st.error(f"Cancel failed: {e}")
            if action == "Modify":
                new_price = st.number_input("New Price", min_value=0.0)
                new_qty = st.number_input("New Quantity", min_value=1)
                if st.button("Modify Order"):
                    try:
                        order = df[df["order_id"] == order_id].iloc[0].to_dict()
                        resp = io.modify_order(
                            order_id=order_id,
                            price=new_price,
                            quantity=int(new_qty),
                            price_type=order.get("price_type", "LIMIT"),
                            exchange=order.get("exchange", "NSE"),
                            order_type=order.get("order_type", "BUY"),
                            product_type=order.get("product_type", "CNC"),
                            tradingsymbol=order.get("tradingsymbol", symbol)
                        )
                        st.success(f"Modified order {order_id}: {resp}")
                    except Exception as e:
                        st.error(f"Modify failed: {e}")
    except Exception as e:
        st.error(f"Order book error: {e}")

elif section == "🔄 Session Status":
    st.header("Session Status")
    st.write("API token", api_token)
    st.write("Session keys", api_session_key)
    st.write("WS session key", ws_session_key)
    st.info("If you get a session error, restart the app or refresh session keys in secrets.")

st.sidebar.markdown("---")
st.sidebar.markdown("**Powered by Definedge API.**")
