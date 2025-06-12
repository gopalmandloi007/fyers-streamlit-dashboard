import streamlit as st
import pandas as pd
from fyers_apiv3 import fyersModel
import datetime
import time

# ------------- Fyers Login (from Streamlit secrets) -------------
client_id = st.secrets["client_id"]
access_token = st.secrets["access_token"]
fyers = fyersModel.FyersModel(client_id=client_id, token=access_token)

# ------------- Helper Functions -------------
def get_full_symbol(symbol):
    if symbol.startswith("NSE:"):
        return symbol
    return f"NSE:{symbol.upper()}-EQ"

@st.cache_data(show_spinner="Fetching previous close...")
def get_prev_trading_close(symbol):
    today = datetime.datetime.now().date()
    for i in range(1, 10):
        dt = today - datetime.timedelta(days=i)
        dt_str = dt.strftime("%Y-%m-%d")
        data = {
            "symbol": symbol,
            "resolution": "1D",
            "date_format": "1",
            "range_from": dt_str,
            "range_to": dt_str,
            "cont_flag": "1"
        }
        try:
            candles = fyers.history(data)
            if candles.get('code') == 200 and candles.get('candles'):
                prev_close = candles['candles'][0][4]
                return prev_close
        except:
            time.sleep(0.2)
    return None

def fetch_ltp(symbol):
    try:
        quote = fyers.quotes({"symbols": symbol})
        return float(quote['d'][0]['v']['lp'])
    except:
        return 0

def place_order(symbol, side, product, order_type, qty, limit_price, stop_price, order_tag):
    PRODUCT_MAP = {1: "CNC", 2: "INTRADAY", 3: "CO", 4: "BO"}
    ORDER_TYPE_MAP = {1: "LIMIT", 2: "MARKET", 3: "SL-M", 4: "SL-L"}
    order = {
        "symbol": symbol,
        "qty": int(qty),
        "type": 1 if side == 1 else 2,
        "side": 1 if side == 1 else -1,
        "productType": PRODUCT_MAP[product],
        "orderType": ORDER_TYPE_MAP[order_type],
        "limitPrice": float(limit_price) if order_type in [1,4] else 0,
        "stopPrice": float(stop_price) if order_type in [3,4] else 0,
        "disclosedQty": 0,
        "validity": "DAY",
        "offlineOrder": False
    }
    if order_tag: order["orderTag"] = order_tag
    return fyers.place_order(order)

def cancel_order(order_id):
    return fyers.cancel_order({"id": order_id})

def modify_order(order_id, order_type, qty, limit_price, stop_price):
    disclosed_qty = max(1, int(qty * 0.1))
    data = {
        "id": order_id,
        "type": order_type,
        "qty": qty,
        "limitPrice": limit_price,
        "stopPrice": stop_price,
        "disclosedQty": disclosed_qty
    }
    return fyers.modify_order(data=data)

# ------------- Sidebar Navigation -------------
st.sidebar.title("Fyers Dashboard")
menu = st.sidebar.radio("Go to", [
    "Holiday-Aware Holdings",
    "Exit Holdings/Positions",
    "Place Order",
    "Modify/Cancel Order",
    "Order & Trade Book"
])

# ------------- 1. Holiday-Aware Holdings -------------
if menu == "Holiday-Aware Holdings":
    st.header("📊 Holdings (Holiday-Aware)")
    holdings = fyers.holdings()
    if holdings.get("code", 0) == 200 and holdings.get("holdings"):
        holdings_data = holdings["holdings"]
        all_rows = []
        total_today_pnl = 0
        for h in holdings_data:
            symbol = h["symbol"]
            qty = h["quantity"]
            avg = h["costPrice"]
            ltp = h["ltp"]
            invest = avg * qty
            pnl = h["pl"]
            pl_pct = (pnl / invest) * 100 if invest else 0
            prev_close = get_prev_trading_close(symbol)
            today_pnl = (ltp - prev_close) * qty if prev_close and qty else 0
            today_pct = ((ltp - prev_close) / prev_close) * 100 if prev_close else 0
            total_today_pnl += today_pnl
            all_rows.append({
                "Symbol": symbol,
                "Qty": qty,
                "Avg Price": avg,
                "LTP": ltp,
                "Investment": invest,
                "Current Value": invest + pnl,
                "P&L": pnl,
                "P&L %": round(pl_pct,2),
                "Prev Close": prev_close if prev_close else "N/A",
                "Today P&L": round(today_pnl,2),
                "Today %": round(today_pct,2) if prev_close else "N/A"
            })
        st.dataframe(pd.DataFrame(all_rows))
        st.write("### Overall Summary")
        st.write(f"**Total Investment:** {holdings['overall']['total_investment']:.2f}")
        st.write(f"**Total Current Value:** {holdings['overall']['total_current_value']:.2f}")
        st.write(f"**Overall P&L:** {holdings['overall']['total_pl']:.2f}")
        st.write(f"**Today's P&L:** {total_today_pnl:.2f}")
    else:
        st.info("No holdings found.")
    funds = fyers.funds()
    if funds.get("code", 0) == 200 and funds.get("fund_limit"):
        st.write("### Funds")
        st.dataframe(pd.DataFrame([funds["fund_limit"][0]]))
    else:
        st.info("No funds data.")

# ------------- 2. Exit Holdings/Positions -------------
elif menu == "Exit Holdings/Positions":
    st.header("Exit Holdings/Positions")
    holdings = fyers.holdings().get("holdings", [])
    positions = fyers.positions().get("netPositions", [])
    st.subheader("Holdings")
    if holdings:
        df = pd.DataFrame(holdings)
        st.dataframe(df[["symbol", "quantity", "costPrice", "ltp", "pl"]])
        selected = st.multiselect("Select holdings to exit:", [h["symbol"] for h in holdings])
        if st.button("Exit Selected Holdings at MARKET"):
            for h in holdings:
                if h["symbol"] in selected and h["quantity"] > 0:
                    resp = place_order(h["symbol"], 2, 1, 2, h["quantity"], 0, 0, "exitorder")
                    if resp.get("code",0) in [200,1101]:
                        st.success(f"Exited {h['symbol']}")
                    else:
                        st.error(f"{h['symbol']}: {resp.get('message','')}")
    else:
        st.info("No holdings found.")
    st.subheader("Positions")
    if positions:
        df = pd.DataFrame(positions)
        st.dataframe(df[["symbol", "netQty", "buyAvg", "sellAvg", "ltp", "realizedPL", "unrealizedPL", "productType"]])
        selected = st.multiselect("Select positions to exit:", [p["symbol"] for p in positions])
        if st.button("Exit Selected Positions at MARKET"):
            for p in positions:
                if p["symbol"] in selected and abs(p["netQty"]) > 0:
                    resp = place_order(p["symbol"], 2, 2, 2, abs(p["netQty"]), 0, 0, "exitorder")
                    if resp.get("code",0) in [200,1101]:
                        st.success(f"Exited {p['symbol']}")
                    else:
                        st.error(f"{p['symbol']}: {resp.get('message','')}")
    else:
        st.info("No positions found.")

# ------------- 3. Place Order -------------
elif menu == "Place Order":
    st.header("Place Buy/Sell Order")
    with st.form("order_form"):
        symbol = st.text_input("Symbol (e.g. SBIN or NSE:SBIN-EQ)")
        ltp = fetch_ltp(get_full_symbol(symbol)) if symbol else 0
        st.write(f"LTP: {ltp if ltp else 'N/A'}")
        side = st.selectbox("Side", [1,2], format_func=lambda x: "BUY" if x==1 else "SELL")
        product = st.selectbox("Product", [1,2,3,4], format_func=lambda x: {1:"CNC",2:"INTRADAY",3:"CO",4:"BO"}[x])
        order_type = st.selectbox("Order Type", [1,2,3,4], format_func=lambda x: {1:"LIMIT",2:"MARKET",3:"SL-M",4:"SL-L"}[x])
        qty_mode = st.radio("Entry Mode", ["Quantity", "Amount (INR)"])
        qty = st.number_input("Quantity", min_value=1) if qty_mode=="Quantity" else 0
        amount = st.number_input("Amount (INR)", min_value=1) if qty_mode=="Amount (INR)" else 0
        limit_price = st.number_input("Limit Price", value=ltp or 0.0) if order_type in [1,4] else 0
        stop_price = st.number_input("Trigger Price", value=0.0) if order_type in [3,4] else 0
        order_tag = st.text_input("Order Tag (optional)", value="")
        submit = st.form_submit_button("Place Order")
        if submit and symbol:
            symbol_full = get_full_symbol(symbol)
            final_qty = qty
            if qty_mode == "Amount (INR)":
                price = limit_price if order_type in [1,4] else ltp
                final_qty = max(1, int(amount // price)) if price else 0
            resp = place_order(symbol_full, side, product, order_type, final_qty, limit_price, stop_price, order_tag)
            if resp.get("code",0) in [200,1101]:
                st.success(f"Order placed! Order ID: {resp.get('id','')}")
            else:
                st.error(f"Order failed: {resp.get('message','')}")

# ------------- 4. Modify/Cancel Order -------------
elif menu == "Modify/Cancel Order":
    st.header("Modify/Cancel Orders")
    orders = fyers.orderbook().get("orderBook", [])
    pending = [o for o in orders if int(o.get("status",0)) in [1,6] and int(o.get("remainingQuantity",0)) > 0]
    if not pending:
        st.info("No pending orders.")
    else:
        df = pd.DataFrame(pending)
        st.dataframe(df[["id","symbol","qty","remainingQuantity","filledQty","status","limitPrice","stopPrice","type","productType"]])
        action = st.selectbox("Action", ["Cancel", "Modify"])
        selected_ids = st.multiselect("Select Order IDs:", [o["id"] for o in pending])
        if action == "Cancel" and st.button("Cancel Selected Orders"):
            for oid in selected_ids:
                resp = cancel_order(oid)
                if resp.get("code",0) == 200:
                    st.success(f"Cancelled {oid}")
                else:
                    st.error(f"Failed to cancel {oid}: {resp.get('message','')}")
        if action == "Modify" and st.button("Modify Selected Orders"):
            for oid in selected_ids:
                st.write(f"Modify Order {oid}")
                order_type = st.selectbox(f"Order Type for {oid}", [1,2,3,4], key=f"ot_{oid}")
                qty = st.number_input(f"New Qty for {oid}", min_value=1, key=f"qty_{oid}")
                limit_price = st.number_input(f"New Limit Price for {oid}", value=0.0, key=f"lp_{oid}")
                stop_price = st.number_input(f"New Stop Price for {oid}", value=0.0, key=f"sp_{oid}")
                if st.button(f"Submit Modification for {oid}"):
                    resp = modify_order(oid, order_type, qty, limit_price, stop_price)
                    if resp.get("code",0) == 200:
                        st.success(f"Modified {oid}")
                    else:
                        st.error(f"Failed to modify {oid}: {resp.get('message','')}")

# ------------- 5. Order & Trade Book -------------
elif menu == "Order & Trade Book":
    st.header("Order Book")
    orders = fyers.orderbook().get("orderBook", [])
    if not orders:
        st.info("No order data.")
    else:
        df = pd.DataFrame(orders)
        st.dataframe(df)
    st.header("Trade Book")
    trades = fyers.tradebook().get("tradeBook", [])
    if not trades:
        st.info("No trade data.")
    else:
        df = pd.DataFrame(trades)
        st.dataframe(df)
