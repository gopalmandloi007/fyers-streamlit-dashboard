import streamlit as st
import pandas as pd
from integrate import ConnectToIntegrate, IntegrateOrders
import requests
from datetime import datetime, timedelta

# --- Load secrets
api_token = st.secrets["integrate_api_token"]
api_secret = st.secrets["integrate_api_secret"]
uid = st.secrets["integrate_uid"]
actid = st.secrets["integrate_actid"]
api_session_key = st.secrets["integrate_api_session_key"]
ws_session_key = st.secrets["integrate_ws_session_key"]

# --- API setup
conn = ConnectToIntegrate()
conn.login(api_token, api_secret)
conn.set_session_keys(uid, actid, api_session_key, ws_session_key)
io = IntegrateOrders(conn)

def get_definedge_ltp_and_yclose(segment, token, session_key, max_days_lookback=10):
    headers = {'Authorization': session_key}
    ltp = None
    try:
        url = f"https://integrate.definedgesecurities.com/dart/v1/quotes/{segment}/{token}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            ltp = float(data.get('ltp')) if data.get('ltp') not in (None, "null", "") else None
    except Exception:
        pass

    yclose = None
    closes = []
    for offset in range(1, max_days_lookback+1):
        dt = datetime.now() - timedelta(days=offset-1)
        date_str = dt.strftime('%d%m%Y')
        from_time = f"{date_str}0000"
        to_time = f"{date_str}1530"
        url = f"https://data.definedgesecurities.com/sds/history/{segment}/{token}/day/{from_time}/{to_time}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                lines = response.text.strip().splitlines()
                for line in lines:
                    fields = line.split(',')
                    if len(fields) >= 5:
                        closes.append(float(fields[4]))
                if len(closes) >= 2:
                    break
        except Exception:
            pass
        if len(closes) >= 2:
            break
    closes = list(dict.fromkeys(closes))
    if len(closes) >= 2:
        yclose = closes[-2]
    return ltp, yclose

def build_master_mapping_from_holdings(holdings_book):
    mapping = {}
    raw = holdings_book.get('data', [])
    if not isinstance(raw, list):
        return mapping
    for h in raw:
        tradingsymbols = h.get("tradingsymbol")
        if isinstance(tradingsymbols, list):
            for ts in tradingsymbols:
                exch = ts.get("exchange", "NSE")
                tsym = ts.get("tradingsymbol", "")
                token = ts.get("token", "")
                if exch and tsym and token:
                    mapping[(exch, tsym)] = {'segment': exch, 'token': token}
    return mapping

def holdings_tabular(holdings_book, master_mapping, session_key):
    raw = holdings_book.get('data', [])
    table = []
    total_today_pnl = 0
    total_overall_pnl = 0
    total_invested = 0
    total_current = 0

    headers = [
        "Symbol", "LTP", "Avg Buy", "Qty", "P.Close", "%Chg", "Today P&L", "Overall P&L",
        "%Chg Avg", "Invested", "Current", "Exchange", "ISIN"
    ]

    for h in raw:
        dp_qty = float(h.get("dp_qty", 0) or 0)
        avg_buy_price = float(h.get("avg_buy_price", 0) or 0)
        tradingsymbols = h.get("tradingsymbol")
        if isinstance(tradingsymbols, list):
            for ts in tradingsymbols:
                exch = ts.get("exchange", "NSE")
                if exch != "NSE":
                    continue
                tsym = ts.get("tradingsymbol", "N/A")
                isin = ts.get("isin", "N/A")
                key = (exch, tsym)
                segment_token = master_mapping.get(key)
                if not segment_token:
                    ltp, yest_close = None, None
                else:
                    ltp, yest_close = get_definedge_ltp_and_yclose(segment_token['segment'], segment_token['token'], session_key)
                holding_qty = dp_qty if dp_qty > 0 else 0

                invested = avg_buy_price * holding_qty
                current = (ltp or 0) * holding_qty if ltp is not None else 0
                today_pnl = (ltp - yest_close) * holding_qty if ltp is not None and yest_close is not None else 0
                overall_pnl = (ltp - avg_buy_price) * holding_qty if ltp is not None else 0
                pct_change = ((ltp - yest_close) / yest_close * 100) if ltp is not None and yest_close not in (None, 0) else None
                pct_change_avg = ((ltp - avg_buy_price) / avg_buy_price * 100) if ltp is not None and avg_buy_price not in (None, 0) else None

                total_today_pnl += today_pnl
                total_overall_pnl += overall_pnl
                total_invested += invested
                total_current += current

                table.append([
                    tsym,
                    f"{ltp:.2f}" if ltp is not None else "N/A",
                    f"{avg_buy_price:.2f}",
                    int(holding_qty),
                    f"{yest_close:.2f}" if yest_close is not None else "N/A",
                    f"{pct_change:.2f}" if pct_change is not None else "N/A",
                    f"{today_pnl:.2f}" if today_pnl is not None else "N/A",
                    f"{overall_pnl:.2f}" if overall_pnl is not None else "N/A",
                    f"{pct_change_avg:.2f}" if pct_change_avg is not None else "N/A",
                    f"{invested:.2f}",
                    f"{current:.2f}",
                    exch,
                    isin
                ])
    df = pd.DataFrame(table, columns=headers)
    summary = {
        "Today P&L": round(total_today_pnl, 2),
        "Overall P&L": round(total_overall_pnl, 2),
        "Total Invested": round(total_invested, 2),
        "Total Current": round(total_current, 2)
    }
    return df, summary

def positions_tabular(positions_book):
    raw = positions_book.get('positions', [])
    table = []
    headers = [
        "Symbol", "Avg. Buy", "Qty", "Unrealised P&L", "Realized P&L", "% Change", "Product Type"
    ]
    for p in raw:
        tsym = p.get("tradingsymbol", "")
        avg_buy = p.get("net_averageprice", "")
        qty = p.get("net_quantity", "")
        unreal = p.get("unrealized_pnl", "")
        realized = p.get("realized_pnl", "")
        try:
            last_price = float(p.get("lastPrice", 0))
            avg_price = float(avg_buy if avg_buy not in ("", None) else 0)
            pct_change = round((last_price - avg_price) / avg_price * 100, 2) if avg_price else "N/A"
        except Exception:
            pct_change = "N/A"
        prod = p.get("product_type", "")
        table.append([tsym, avg_buy, qty, unreal, realized, pct_change, prod])
    df = pd.DataFrame(table, columns=headers)
    return df

st.set_page_config(page_title="Perfect Holdings / Positions (Live LTP & P&L)", layout="wide")
st.title("Perfect Holdings / Positions (Live LTP & P&L)")

# Holdings
st.header("Holdings")
try:
    holdings_book = io.holdings()
    if not holdings_book.get("data"):
        st.info("No holdings found or API returned: " + str(holdings_book))
    else:
        master_mapping = build_master_mapping_from_holdings(holdings_book)
        df_hold, summary = holdings_tabular(holdings_book, master_mapping, api_session_key)
        st.write("**Summary**")
        st.write(summary)
        st.dataframe(df_hold)
except Exception as e:
    st.error(f"Failed to get holdings: {e}")

# Positions
st.header("Positions")
try:
    positions_book = io.positions()
    if not positions_book.get("positions"):
        st.info("No positions found or API returned: " + str(positions_book))
    else:
        df_pos = positions_tabular(positions_book)
        st.dataframe(df_pos)
except Exception as e:
    st.error(f"Failed to get positions: {e}")
