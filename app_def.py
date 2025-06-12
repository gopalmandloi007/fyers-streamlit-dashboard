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

                table.append({
                    "Symbol": tsym,
                    "LTP": ltp,
                    "Avg Buy": avg_buy_price,
                    "Qty": holding_qty,
                    "Prev Close": yest_close,
                    "% Chg": pct_change,
                    "Today P&L": today_pnl,
                    "Overall P&L": overall_pnl,
                    "% Chg Avg": pct_change_avg,
                    "Invested": invested,
                    "Current": current,
                    "Exchange": exch,
                    "ISIN": isin
                })
    df = pd.DataFrame(table)
    summary = {
        "Today P&L": total_today_pnl,
        "Overall P&L": total_overall_pnl,
        "Total Invested": total_invested,
        "Total Current": total_current
    }
    return df, summary

def positions_tabular(positions_book):
    raw = positions_book.get('positions', [])
    df = pd.DataFrame(raw)
    if not df.empty:
        df["% Change"] = df.apply(
            lambda p: round((float(p.get("lastPrice", 0)) - float(p.get("net_averageprice", 0))) / float(p.get("net_averageprice", 1)) * 100, 2)
            if float(p.get("net_averageprice", 0)) else None,
            axis=1
        )
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
        if not df_hold.empty:
            st.dataframe(df_hold)
            st.write("**Summary**")
            st.write(summary)
        else:
            st.info("No NSE holdings found.")
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
        if not df_pos.empty:
            st.dataframe(df_pos)
        else:
            st.info("No positions data in API result.")
except Exception as e:
    st.error(f"Failed to get positions: {e}")
