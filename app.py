import streamlit as st
import pandas as pd
from fyers_apiv3 import fyersModel
import datetime
import time

# --- Load credentials securely from secrets ---
client_id = st.secrets["client_id"]
access_token = st.secrets["access_token"]
fyers = fyersModel.FyersModel(client_id=client_id, token=access_token)

# --- Utility: Holiday-aware previous close for a symbol ---
@st.cache_data(show_spinner="Fetching previous close...")
def get_prev_trading_close(symbol, upto_date=None):
    if upto_date is None:
        upto_date = datetime.datetime.now().date()
    else:
        upto_date = pd.to_datetime(upto_date).date()
    for days_ago in range(1, 10):
        dt = upto_date - datetime.timedelta(days=days_ago)
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
                return prev_close, dt_str
        except Exception:
            time.sleep(0.5)
            continue
    return None, None

def get_full_symbol(symbol):
    if symbol.startswith("NSE:"):
        return symbol
    return f"NSE:{symbol.upper()}-EQ"

def fetch_ltp(symbol):
    try:
        quote = fyers.quotes({"symbols": symbol})
        return float(quote['d'][0]['v']['lp'])
    except Exception:
        return None

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
    if order_tag:
        order["orderTag"] = order_tag
    return fyers.place_order(order)

def modify_order(order_id, order_type, qty, limit_price=0, stop_price=0):
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

def cancel_order(order_id):
    data = {"id": order_id}
    return fyers.cancel_order(data=data)

def exit_asset(symbol, qty, product_type):
    return place_order(symbol, 2, 1 if product_type == "CNC" else 2, 2, qty, 0, 0, "exitorder")

# --- Sidebar Navigation ---
st.sidebar.title("Fyers Trading Dashboard")
section = st.sidebar.radio(
    "Go to", [
        "📊 Holdings (Holiday-Aware)",
        "📈 Holdings/Positions Exit",
        "🛒 Place Order",
        "🛠️ Modify/Cancel Order",
        "📒 Order & Trade Book"
    ]
)

# --- 1. Holiday-Aware Holdings Dashboard ---
if section == "📊 Holdings (Holiday-Aware)":
    st.header("📊 Holdings & Positions Dashboard (Holiday-Aware)")

    holdings = fyers.holdings()
    if holdings.get("code") == 200 and holdings.get("holdings"):
        holdings_data = holdings.get("holdings", [])
        overall = holdings.get("overall", {})

        st.subheader("Holdings Details")
        rows = []
        total_today_pnl = 0
        prev_close_cache = {}
        for holding in sorted(holdings_data, key=lambda x: x.get('symbol', '')):
            symbol = holding.get('symbol', '')
            ltp = holding.get('ltp', 0)
            qty = holding.get('quantity', 0)
            investment = holding.get('costPrice', 0) * qty
            pl_percent = (holding.get('pl', 0) / investment) * 100 if investment != 0 else 0
            current_value = investment + holding.get('pl', 0)

            # Prev close (cache to avoid rate limits)
            if symbol not in prev_close_cache:
                prev_close, _ = get_prev_trading_close(symbol)
                prev_close_cache[symbol] = prev_close
            else:
                prev_close = prev_close_cache[symbol]
            today_pnl = 0
            today_perc = 0
            if prev_close is not None and qty > 0:
                today_pnl = (ltp - prev_close) * qty
                today_perc = ((ltp - prev_close) / prev_close) * 100 if prev_close != 0 else 0
                total_today_pnl += today_pnl
            rows.append({
                "Symbol": symbol,
                "Current P&L": holding.get('pl', 0),
                "P&L %": round(pl_percent, 2),
                "Quantity": qty,
                "Avg Price": holding.get('costPrice', 0),
                "LTP": ltp,
                "Today %Change": round(today_perc, 2) if prev_close is not None else "N/A",
                "Investment": investment,
                "Current Value": current_value,
                "Prev Close": prev_close if prev_close is not None else "N/A",
                "Today P&L": round(today_pnl, 2)
            })
        hdf = pd.DataFrame(rows)
        st.dataframe(hdf, use_container_width=True)

        st.subheader("Overall Summary")
        summary = pd.DataFrame([
            ["Total Investment", overall.get('total_investment', 0)],
            ["Total Current Value", overall.get('total_current_value', 0)],
            ["Overall P&L", overall.get('total_pl', 0)],
            ["Today's P&L", round(total_today_pnl, 2)]
        ], columns=["Metric", "Value"])
        st.dataframe(summary, use_container_width=True)
    else:
        st.warning("No holdings data available.")

    # Positions
    positions = fyers.positions()
    if positions.get("code") == 200 and positions.get("netPositions"):
        st.subheader("Positions")
        pdata = []
        for p in sorted(positions["netPositions"], key=lambda x: x.get('symbol','')):
            if p.get('realizedPL', 0) != 0 or p.get('unrealizedPL', 0) != 0:
                pdata.append({
                    "Symbol": p.get('symbol', ''),
                    "Net Qty": p.get('netQty', 0),
                    "Buy Qty": p.get('buyQty', 0),
                    "Sell Qty": p.get('sellQty', 0),
                    "Buy Avg": p.get('buyAvg', 0),
                    "Sell Avg": p.get('sellAvg', 0),
                    "LTP": p.get('ltp', 0),
                    "Realized P&L": p.get('realizedPL', 0),
                    "Unrealized P&L": p.get('unrealizedPL', 0)
                })
        if pdata:
            st.dataframe(pd.DataFrame(pdata), use_container_width=True)
        else:
            st.info("No P&L in positions.")
    else:
        st.warning("No positions data available.")

    # Funds
    funds = fyers.funds()
    if funds.get("code") == 200 and funds.get("fund_limit"):
        st.subheader("Available Funds")
        fd = funds["fund_limit"][0]
        fund_tbl = pd.DataFrame([
            ["Available Funds", fd.get('availableFunds', 0)],
            ["Used Margin", fd.get('usedMargin', 0)],
            ["Net Funds", fd.get('netFunds', 0)],
            ["Total Collateral", fd.get('totalCollateral', 0)]
        ], columns=["Metric", "Value"])
        st.dataframe(fund_tbl, use_container_width=True)
    else:
        st.warning("No funds data available.")

# --- 2. Holdings / Positions Exit ---
elif section == "📈 Holdings/Positions Exit":
    st.header("Exit Holdings & Positions")
    holdings = fyers.holdings().get("holdings", [])
    positions = fyers.positions().get("netPositions", [])

    st.subheader("Holdings")
    if not holdings:
        st.info("No holdings found.")
    else:
        hdf = pd.DataFrame(holdings)
        st.dataframe(hdf[["symbol", "quantity", "costPrice", "ltp", "pl"]])
        selected_h = st.multiselect("Select holdings to exit (by symbol):", [h['symbol'] for h in holdings])
        if st.button("Exit Selected Holdings at MARKET"):
            for h in holdings:
                if h['symbol'] in selected_h and h['quantity'] > 0:
                    resp = exit_asset(h['symbol'], h['quantity'], "CNC")
                    if resp.get("code") in [200, 1101]:
                        st.success(f"Exited {h['symbol']} (Order ID: {resp.get('id','')})")
                    else:
                        st.error(f"{h['symbol']}: {resp.get('message','')}")
        if st.button("Exit ALL Holdings at MARKET"):
            for h in holdings:
                if h['quantity'] > 0:
                    resp = exit_asset(h['symbol'], h['quantity'], "CNC")
                    if resp.get("code") in [200, 1101]:
                        st.success(f"Exited {h['symbol']} (Order ID: {resp.get('id','')})")
                    else:
                        st.error(f"{h['symbol']}: {resp.get('message','')}")
    st.markdown("---")
    st.subheader("Positions")
    if not positions:
        st.info("No positions found.")
    else:
        pdf = pd.DataFrame(positions)
        st.dataframe(pdf[["symbol", "netQty", "buyAvg", "sellAvg", "ltp", "realizedPL", "unrealizedPL", "productType"]])
        selected_p = st.multiselect("Select positions to exit (by symbol):", [p['symbol'] for p in positions])
        if st.button("Exit Selected Positions at MARKET"):
            for p in positions:
                if p['symbol'] in selected_p and abs(p['netQty']) > 0:
                    resp = exit_asset(p['symbol'], abs(p['netQty']), p['productType'])
                    if resp.get("code") in [200, 1101]:
                        st.success(f"Exited {p['symbol']} (Order ID: {resp.get('id','')})")
                    else:
                        st.error(f"{p['symbol']}: {resp.get('message','')}")
        if st.button("Exit ALL Positions at MARKET"):
            for p in positions:
                if abs(p['netQty']) > 0:
                    resp = exit_asset(p['symbol'], abs(p['netQty']), p['productType'])
                    if resp.get("code") in [200, 1101]:
                        st.success(f"Exited {p['symbol']} (Order ID: {resp.get('id','')})")
                    else:
                        st.error(f"{p['symbol']}: {resp.get('message','')}")

# --- 3. Place Order ---
elif section == "🛒 Place Order":
    st.header("Place Buy/Sell Order")
    with st.form("order_form"):
        symbol = st.text_input("Symbol (e.g. SBIN or NSE:SBIN-EQ)")
        ltp = fetch_ltp(get_full_symbol(symbol)) if symbol else None
        st.write(f"LTP: {ltp if ltp else 'N/A'}")
        side = st.selectbox("Side", [1, 2], format_func=lambda x: "BUY" if x == 1 else "SELL")
        product = st.selectbox("Product", [1, 2, 3, 4], format_func=lambda x: {1:"CNC",2:"INTRADAY",3:"CO",4:"BO"}[x])
        order_type = st.selectbox("Order Type", [1, 2, 3, 4], format_func=lambda x: {1:"LIMIT",2:"MARKET",3:"SL-M",4:"SL-L"}[x])
        qty_mode = st.radio("Entry Mode", ["Quantity", "Amount (INR)"])
        qty = st.number_input("Quantity", min_value=1, step=1) if qty_mode == "Quantity" else 0
        amount = st.number_input("Amount (INR)", min_value=1) if qty_mode == "Amount (INR)" else 0
        limit_price = st.number_input("Limit Price", value=ltp or 0.0) if order_type in [1,4] else 0
        stop_price = st.number_input("Trigger Price", value=0.0) if order_type in [3,4] else 0
        order_tag = st.text_input("Order Tag (optional)", value="")
        submit = st.form_submit_button("Place Order")
        if submit and symbol:
            symbol_full = get_full_symbol(symbol)
            final_qty = qty
            if qty_mode == "Amount (INR)":
                price_for_calc = limit_price if order_type in [1,4] else ltp
                final_qty = max(1, int(amount // price_for_calc)) if price_for_calc else 0
            st.write(f"Final order: {final_qty} shares of {symbol_full}")
            resp = place_order(
                symbol_full, side, product, order_type, final_qty, limit_price, stop_price, order_tag
            )
            if resp.get("code") in [200, 1101]:
                st.success(f"Order placed! Order ID: {resp.get('id','')}")
            else:
                st.error(f"Order failed: {resp.get('message','')}")

# --- 4. Modify/Cancel Order ---
elif section == "🛠️ Modify/Cancel Order":
    st.header("Modify/Cancel Pending Orders")
    orders = fyers.orderbook().get("orderBook", [])
    pending = [o for o in orders if int(o.get("status", 0)) in [1,6] and int(o.get("remainingQuantity",0)) > 0]
    if not pending:
        st.info("No pending orders for modification/cancellation.")
    else:
        odf = pd.DataFrame(pending)
        st.dataframe(odf[["id","symbol","qty","remainingQuantity","filledQty","status","limitPrice","stopPrice","type","productType"]])
        action = st.selectbox("Action", ["Cancel", "Modify"])
        selected_orders = st.multiselect("Select Order IDs:", [o['id'] for o in pending])
        if action == "Cancel" and st.button("Cancel Selected Orders"):
            for oid in selected_orders:
                resp = cancel_order(oid)
                if resp.get("code") == 200:
                    st.success(f"Cancelled order {oid}")
                else:
                    st.error(f"Failed to cancel {oid}: {resp.get('message','')}")
        elif action == "Modify" and st.button("Modify Selected Orders"):
            for oid in selected_orders:
                st.write(f"Modify Order {oid}")
                order_type = st.selectbox(f"Order Type for {oid}", [1,2,3,4], key=f"ot_{oid}")
                qty = st.number_input(f"New Qty for {oid}", min_value=1, step=1, key=f"qty_{oid}")
                limit_price = st.number_input(f"New Limit Price for {oid}", value=0.0, key=f"lp_{oid}")
                stop_price = st.number_input(f"New Stop Price for {oid}", value=0.0, key=f"sp_{oid}")
                if st.button(f"Submit Modification for {oid}"):
                    resp = modify_order(oid, order_type, qty, limit_price, stop_price)
                    if resp.get("code") == 200:
                        st.success(f"Modified order {oid}")
                    else:
                        st.error(f"Failed to modify {oid}: {resp.get('message','')}")

# --- 5. Order & Trade Book ---
elif section == "📒 Order & Trade Book":
    st.header("Order Book")
    orders = fyers.orderbook().get("orderBook", [])
    if not orders:
        st.info("No order data.")
    else:
        df = pd.DataFrame(orders)
        df["Status"] = df.apply(lambda row: (
            "Completed" if row.get("filledQty",0)==row.get("qty",0) and row.get("qty",0)>0 else
            "Partially Filled" if row.get("filledQty",0)>0 and row.get("filledQty",0)<row.get("qty",0) else
            "Pending" if row.get("remainingQuantity",0)>0 and row.get("filledQty",0)==0 else
            "Cancelled" if int(row.get("status",0))==3 else
            "Rejected" if int(row.get("status",0))==4 else
            "Expired" if int(row.get("status",0))==5 else
            "Open" if int(row.get("status",0))==6 else
            "Trigger Pending" if int(row.get("status",0))==7 else "Unknown"
        ), axis=1)
        st.dataframe(df[["id","symbol","qty","remainingQuantity","filledQty","Status","limitPrice","stopPrice","orderDateTime","orderTag"]])

    st.header("Trade Book")
    trades = fyers.tradebook().get("tradeBook", [])
    if not trades:
        st.info("No trade data.")
    else:
        tdf = pd.DataFrame(trades)
        st.dataframe(tdf[["orderNumber","tradeNumber","symbol","tradePrice","tradedQty","side","productType","orderDateTime","tradeValue","orderTag"]])
