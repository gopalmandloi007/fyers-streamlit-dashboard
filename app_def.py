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
    total_realized_today = 0
    total_realized_overall = 0

    headers = [
        "Symbol", "LTP", "Avg Buy", "Qty", "P.Close", "%Chg", "Today P&L", "Overall P&L",
        "Realized P&L", "%Chg Avg", "Invested", "Current", "Exchange", "ISIN", "T1", "Haircut", "Coll Qty", "Sell Amt", "Trade Qty"
    ]

    for h in raw:
        dp_qty = float(h.get("dp_qty", 0) or 0)
        avg_buy_price = float(h.get("avg_buy_price", 0) or 0)
        t1_qty = h.get("t1_qty", "N/A")
        haircut = h.get("haircut", "N/A")
        collateral_qty = h.get("collateral_qty", "N/A")
        sell_amt = float(h.get("sell_amt", 0) or 0)
        trade_qty = float(h.get("trade_qty", 0) or 0)
        tradingsymbols = h.get("tradingsymbol")
        realized_pnl = 0.0

        if isinstance(tradingsymbols, list) and tradingsymbols:
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
                exited = (sell_amt > 0 and trade_qty > 0)
                holding_qty = dp_qty if dp_qty > 0 else 0
                exited_qty = trade_qty if exited else 0

                if exited and exited_qty > 0:
                    sell_price = sell_amt / exited_qty if exited_qty else 0
                    realized_pnl = (sell_price - avg_buy_price) * exited_qty
                    total_realized_today += realized_pnl
                    total_realized_overall += realized_pnl
                else:
                    realized_pnl = 0

                if holding_qty > 0:
                    invested = avg_buy_price * holding_qty
                    current = (ltp or 0) * holding_qty if ltp is not None else 0
                    today_pnl = (ltp - yest_close) * holding_qty if ltp is not None and yest_close is not None else 0
                    overall_pnl = (ltp - avg_buy_price) * holding_qty if ltp is not None else 0
                    pct_change = ((ltp - yest_close) / yest_close * 100) if ltp is not None and yest_close not in (None, 0) else "N/A"
                    pct_change_avg = ((ltp - avg_buy_price) / avg_buy_price * 100) if ltp is not None and avg_buy_price not in (None, 0) else "N/A"
                else:
                    invested = 0
                    current = 0
                    today_pnl = 0
                    overall_pnl = 0
                    pct_change = "N/A"
                    pct_change_avg = "N/A"

                # Totals only from holding qty (unrealized)
                total_today_pnl += today_pnl
                total_overall_pnl += overall_pnl
                total_invested += invested
                total_current += current

                # For display: realized P&L as column
                table.append([
                    tsym,
                    f"{ltp:.2f}" if ltp is not None else "N/A",
                    f"{avg_buy_price:.2f}",
                    int(holding_qty),
                    f"{yest_close:.2f}" if yest_close is not None else "N/A",
                    f"{pct_change:.2f}" if isinstance(pct_change, float) else pct_change,
                    f"{today_pnl:.2f}" if isinstance(today_pnl, float) else today_pnl,
                    f"{overall_pnl:.2f}" if isinstance(overall_pnl, float) else overall_pnl,
                    f"{realized_pnl:.2f}" if realized_pnl else "",
                    f"{pct_change_avg:.2f}" if isinstance(pct_change_avg, float) else pct_change_avg,
                    f"{invested:.2f}",
                    f"{current:.2f}",
                    exch,
                    isin,
                    t1_qty,
                    haircut,
                    collateral_qty,
                    f"{sell_amt:.2f}",
                    int(trade_qty)
                ])

    # Add realized P&L from exited qty to totals
    total_today_pnl += total_realized_today
    total_overall_pnl += total_realized_overall

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
    if not raw or len(raw) == 0:
        return pd.DataFrame()
    headers = list(raw[0].keys())
    important_cols = [
        ("tradingsymbol", "Symbol"),
        ("net_averageprice", "Avg. Buy"),
        ("net_quantity", "Qty"),
        ("unrealized_pnl", "Unrealised P&L"),
        ("realized_pnl", "Realized P&L"),
        ("percent_change", "% Change"),
        ("product_type", "Product Type"),
    ]
    all_keys = list(raw[0].keys()) if raw else []
    rest_keys = [k for k in all_keys if k not in [col[0] for col in important_cols]]
    headers = [col[1] for col in important_cols] + rest_keys
    total_unrealized = 0.0
    total_realized = 0.0
    for p in raw:
        try:
            last_price = float(p.get("lastPrice", 0))
            avg_price = float(p.get("net_averageprice", 0))
            if avg_price:
                percent_change = round((last_price - avg_price) / avg_price * 100, 2)
            else:
                percent_change = "N/A"
        except Exception:
            percent_change = "N/A"
        row = [p.get(col[0], "") for col in important_cols[:-2]]
        row.append(percent_change)
        row.append(p.get("product_type", ""))
        row += [p.get(k, "") for k in rest_keys]
        table.append(row)
        try:
            total_unrealized += float(p.get("unrealized_pnl", 0) or 0)
        except Exception:
            pass
        try:
            total_realized += float(p.get("realized_pnl", 0) or 0)
        except Exception:
            pass

    summary_table = [
        ["Total Realized P&L", round(total_realized, 2)],
        ["Total Unrealized P&L", round(total_unrealized, 2)],
        ["Total Net P&L", round(total_realized + total_unrealized, 2)]
    ]
    df_sum = pd.DataFrame(summary_table, columns=["Summary", "Amount"])
    df = pd.DataFrame(table, columns=headers)
    return df_sum, df

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
        st.write(f"**Total NSE Holdings: {len(df_hold)}**")
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
        df_sum, df_pos = positions_tabular(positions_book)
        st.write("**Summary**")
        st.dataframe(df_sum)
        st.write(f"**Total NSE Positions: {len(df_pos)}**")
        st.dataframe(df_pos)
except Exception as e:
    st.error(f"Failed to get positions: {e}")
