import streamlit as st
import pandas as pd
from integrate import ConnectToIntegrate, IntegrateOrders

# --- Definedge Credentials from Streamlit secrets ---
definedge_api_token = st.secrets["definedge_api_token"]
definedge_api_secret = st.secrets["definedge_api_secret"]

# --- Connect & Session Management ---
@st.cache_resource
def get_integrate_orders():
    conn = ConnectToIntegrate()
    conn.login(api_token=definedge_api_token, api_secret=definedge_api_secret)
    io = IntegrateOrders(conn)
    return io

io = get_integrate_orders()

# --- Sidebar Navigation ---
st.sidebar.title("Definedge Dashboard")
section = st.sidebar.radio(
    "Go to", [
        "📊 Holdings (Live LTP & P&L)",
        "📈 Exit Holdings/Positions",
        "🛒 Place Order",
        "🛠️ Modify/Cancel Order",
        "📒 Order & Trade Book",
        "🔔 GTT/OCO Orders (Place)",
        "🔔 GTT/OCO Modify/Cancel"
    ]
)

# --- 1. Holdings ---
if section == "📊 Holdings (Live LTP & P&L)":
    st.header("📊 Holdings (Live LTP & P&L)")
    try:
        holdings_raw = io.holdings()
        data = holdings_raw.get("data", [])
        rows = []
        for h in data:
            ts_list = h.get("tradingsymbol", [])
            for ts in ts_list:
                if ts.get("exchange") == "NSE":
                    symbol = ts.get("tradingsymbol")
                    isin = ts.get("isin")
                    token = ts.get("token")
                    qty = float(h.get("dp_qty", 0) or 0)
                    avg = float(h.get("avg_buy_price", 0) or 0)
                    ltp = None
                    try:
                        import requests
                        ltp_url = io.conn.BASE_URL + f"/quotes/NSE/{token}"
                        resp = requests.get(ltp_url, headers=io.conn.headers)
                        ltp = float(resp.json().get("ltp", 0))
                    except Exception:
                        ltp = 0
                    invest = avg * qty
                    pnl = (ltp - avg) * qty if ltp and avg else 0
                    rows.append({
                        "Symbol": symbol,
                        "ISIN": isin,
                        "Qty": qty,
                        "Avg Price": avg,
                        "LTP": ltp,
                        "Investment": invest,
                        "P&L": pnl,
                        "P&L %": round((pnl / invest) * 100, 2) if invest else 0
                    })
        st.dataframe(pd.DataFrame(rows))
    except Exception as e:
        st.error(f"Failed to fetch holdings: {e}")

# --- 2. Exit Holdings/Positions ---
elif section == "📈 Exit Holdings/Positions":
    st.header("Exit Holdings/Positions")
    try:
        holdings = io.holdings().get("data", [])
        st.subheader("Holdings")
        hflat = []
        for h in holdings:
            for ts in h.get("tradingsymbol", []):
                if ts.get("exchange") == "NSE":
                    hflat.append({
                        "symbol": ts.get("tradingsymbol"),
                        "qty": h.get("dp_qty", 0),
                        "token": ts.get("token")
                    })
        if hflat:
            hdf = pd.DataFrame(hflat)
            st.dataframe(hdf)
            selected = st.multiselect("Select symbols to exit:", list(hdf["symbol"]))
            if st.button("Exit Selected Holdings at MARKET"):
                for h in hflat:
                    if h["symbol"] in selected and float(h["qty"]) > 0:
                        try:
                            resp = io.place_order(
                                tradingsymbol=h["symbol"],
                                exchange="NSE",
                                order_type="SELL",
                                quantity=int(float(h["qty"])),
                                product_type="CNC",
                                price_type="MARKET",
                                price="0"
                            )
                            if resp.get("status", "").lower() in ("ok", "success") or resp.get("code", 0) == 200:
                                st.success(f"Exited {h['symbol']}")
                            else:
                                st.error(f"{h['symbol']}: {resp.get('message','')}")
                        except Exception as e:
                            st.error(f"Order failed: {e}")
        else:
            st.info("No holdings found.")
        st.subheader("Positions")
        pos = io.positions().get("positions", [])
        pflat = []
        for p in pos:
            pflat.append({
                "symbol": p.get("tradingsymbol"),
                "qty": p.get("net_quantity", 0)
            })
        if pflat:
            pdf = pd.DataFrame(pflat)
            st.dataframe(pdf)
            selectedp = st.multiselect("Select positions to exit:", list(pdf["symbol"]))
            if st.button("Exit Selected Positions at MARKET"):
                for p in pflat:
                    if p["symbol"] in selectedp and abs(float(p["qty"])) > 0:
                        try:
                            resp = io.place_order(
                                tradingsymbol=p["symbol"],
                                exchange="NSE",
                                order_type="SELL",
                                quantity=int(abs(float(p["qty"]))),
                                product_type="CNC",
                                price_type="MARKET",
                                price="0"
                            )
                            if resp.get("status", "").lower() in ("ok", "success") or resp.get("code", 0) == 200:
                                st.success(f"Exited {p['symbol']}")
                            else:
                                st.error(f"{p['symbol']}: {resp.get('message','')}")
                        except Exception as e:
                            st.error(f"Order failed: {e}")
        else:
            st.info("No positions found.")
    except Exception as e:
        st.error(f"Exit failed: {e}")

# --- 3. Place Order ---
elif section == "🛒 Place Order":
    st.header("Place Buy/Sell Order")
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
                if resp.get("status", "").lower() in ("ok", "success") or resp.get("code", 0) == 200:
                    st.success(f"Order placed! Order ID: {resp.get('order_id', resp.get('id',''))}")
                else:
                    st.error(f"Order failed: {resp.get('message','')}")
            except Exception as e:
                st.error(f"Order failed: {e}")

# --- 4. Modify/Cancel Order ---
elif section == "🛠️ Modify/Cancel Order":
    st.header("Modify/Cancel Pending Orders")
    try:
        order_book = io.orders().get("orders", [])
        pending = [o for o in order_book if o.get("order_status") in ("NEW", "OPEN", "REPLACED") and int(float(o.get("pending_qty", 0))) > 0]
        if not pending:
            st.info("No pending orders.")
        else:
            df = pd.DataFrame(pending)
            st.dataframe(df[["order_id", "tradingsymbol", "quantity", "pending_qty", "filled_qty", "price", "order_type", "order_status"]])
            order_id = st.selectbox("Select order to modify/cancel:", df["order_id"])
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

# --- 5. Order & Trade Book ---
elif section == "📒 Order & Trade Book":
    st.header("Order Book")
    try:
        orders = io.orders().get("orders", [])
        if not orders:
            st.info("No order data.")
        else:
            st.dataframe(pd.DataFrame(orders))
    except Exception as e:
        st.error(f"Order book error: {e}")
    st.header("Trade Book")
    try:
        try:
            trades = io.tradebook().get("trades", [])
        except:
            trades = io.tradebook().get("data", [])
        if not trades:
            st.info("No trade data.")
        else:
            st.dataframe(pd.DataFrame(trades))
    except Exception as e:
        st.error(f"Trade book error: {e}")

# --- 6. Place GTT/OCO Order ---
elif section == "🔔 GTT/OCO Orders (Place)":
    st.header("Place GTT/OCO Order")
    tab = st.tabs(["Single GTT", "OCO GTT"])
    with tab[0]:
        st.subheader("Single GTT")
        symbol = st.text_input("Symbol", key="gttsymbol")
        qty = st.number_input("Quantity", min_value=1, key="gttqty")
        trigger_price = st.number_input("Trigger Price")
        price = st.number_input("Order Price")
        side = st.selectbox("Side", ["BUY", "SELL"], key="gttside")
        if st.button("Place Single GTT"):
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
                st.success(f"Placed GTT! {resp}")
            except Exception as e:
                st.error(f"GTT place failed: {e}")
    with tab[1]:
        st.subheader("OCO GTT")
        symbol = st.text_input("Symbol", key="ocosymbol")
        target_qty = st.number_input("Target Quantity", min_value=1)
        stoploss_qty = st.number_input("Stoploss Quantity", min_value=1)
        target_price = st.number_input("Target Price")
        stoploss_price = st.number_input("Stoploss Price")
        side = st.selectbox("Side", ["BUY", "SELL"], key="ocoside")
        if st.button("Place OCO GTT"):
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
                st.success(f"Placed OCO GTT! {resp}")
            except Exception as e:
                st.error(f"OCO GTT place failed: {e}")

# --- 7. Modify/Cancel GTT/OCO ---
elif section == "🔔 GTT/OCO Modify/Cancel":
    st.header("Modify/Cancel GTT/OCO Orders")
    try:
        import requests
        url = io.conn.BASE_URL + "/gttorders"
        resp = requests.get(url, headers=io.conn.headers)
        orders = resp.json().get("pendingGTTOrderBook", []) or resp.json().get("gtt_orders", []) or resp.json().get("data", [])
        if not orders:
            st.info("No GTT/OCO orders found.")
        else:
            df = pd.DataFrame(orders)
            st.dataframe(df)
            idx = st.number_input("Select order row number to modify/cancel (1-based)", min_value=1, max_value=len(df))
            action = st.radio("Action", ["Modify", "Cancel"], key="gttaction")
            selected = df.iloc[idx-1]
            alert_id = selected.get("alert_id", selected.get("gtt_id", selected.get("id", "")))
            if action == "Cancel" and st.button("Cancel GTT/OCO Order"):
                try:
                    url = io.conn.BASE_URL + f"/gttcancel/{alert_id}"
                    resp = requests.get(url, headers=io.conn.headers)
                    st.success(f"Cancel result: {resp.json()}")
                except Exception as e:
                    try:
                        url2 = io.conn.BASE_URL + f"/ococancel/{alert_id}"
                        resp2 = requests.get(url2, headers=io.conn.headers)
                        st.success(f"OCO Cancel result: {resp2.json()}")
                    except Exception as e2:
                        st.error(f"Cancel failed: {e}\n{e2}")
            if action == "Modify":
                if "stoploss_price" in selected or "target_price" in selected:
                    # OCO modify
                    new_target = st.text_input("New Target Price", value=str(selected.get("target_price", "")))
                    new_stop = st.text_input("New Stoploss Price", value=str(selected.get("stoploss_price", "")))
                    new_target_qty = st.text_input("New Target Qty", value=str(selected.get("target_quantity", "")))
                    new_stop_qty = st.text_input("New Stop Qty", value=str(selected.get("stoploss_quantity", "")))
                    if st.button("Modify OCO GTT"):
                        try:
                            url = io.conn.BASE_URL + "/ocomodify"
                            payload = {
                                "tradingsymbol": selected.get("tradingsymbol"),
                                "exchange": selected.get("exchange"),
                                "order_type": selected.get("order_type"),
                                "target_quantity": new_target_qty,
                                "stoploss_quantity": new_stop_qty,
                                "target_price": new_target,
                                "stoploss_price": new_stop,
                                "alert_id": alert_id,
                                "remarks": "modified by Streamlit"
                            }
                            resp = requests.post(url, headers={**io.conn.headers, "Content-Type": "application/json"}, json=payload)
                            st.success(f"Modify result: {resp.json()}")
                        except Exception as e:
                            st.error(f"OCO modify failed: {e}")
                else:
                    # Single GTT modify
                    new_trigger = st.text_input("New Trigger Price", value=str(selected.get("trigger_price", "")))
                    new_price = st.text_input("New Order Price", value=str(selected.get("price", "")))
                    new_qty = st.text_input("New Qty", value=str(selected.get("quantity", "")))
                    if st.button("Modify Single GTT"):
                        try:
                            url = io.conn.BASE_URL + "/gttmodify"
                            payload = {
                                "exchange": selected.get("exchange"),
                                "alert_id": alert_id,
                                "tradingsymbol": selected.get("tradingsymbol"),
                                "condition": selected.get("condition"),
                                "order_type": selected.get("order_type"),
                                "alert_price": new_trigger,
                                "price": new_price,
                                "quantity": new_qty
                            }
                            resp = requests.post(url, headers={**io.conn.headers, "Content-Type": "application/json"}, json=payload)
                            st.success(f"Modify result: {resp.json()}")
                        except Exception as e:
                            st.error(f"GTT modify failed: {e}")
    except Exception as e:
        st.error(f"GTT book error: {e}")
