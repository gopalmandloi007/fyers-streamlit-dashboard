import streamlit as st
import pandas as pd
import datetime
import time
from fyers_apiv3 import fyersModel

# --- Load credentials from Streamlit secrets ---
client_id = st.secrets["client_id"]
access_token = st.secrets["access_token"]

fyers = fyersModel.FyersModel(client_id=client_id, token=access_token)

# --- Helper functions ---
def get_prev_trading_close_fyers(symbol, upto_date=None):
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

# --- Streamlit App ---
st.set_page_config(page_title="Fyers Holdings Dashboard", layout="wide")
st.title("📈 Fyers Holdings & Positions Dashboard")

if st.button("🔄 Refresh Data"):
    st.session_state['refresh'] = True

if 'refresh' not in st.session_state:
    st.session_state['refresh'] = True

if st.session_state['refresh']:
    # --- Holdings Section ---
    holdings = fyers.holdings()
    if holdings['code'] == 200:
        holdings_data = holdings.get('holdings', [])
        overall_data = holdings.get('overall', {})
        if holdings_data:
            st.subheader("Holdings")
            holdings_table = []
            holdings_headers = [
                "Symbol", "Current P&L", "P&L %", "Quantity",
                "Avg Price", "LTP", "Today %Change", "Investment", "Current Value",
                "Prev Close", "Today P&L"
            ]
            total_today_pnl = 0
            prev_close_cache = {}

            for holding in sorted(holdings_data, key=lambda x: x.get('symbol', '')):
                symbol = holding.get('symbol', '')
                ltp = holding.get('ltp', 0)
                investment = holding.get('costPrice', 0) * holding.get('quantity', 0)
                pl_percent = (holding.get('pl', 0) / investment) * 100 if investment != 0 else 0
                current_value = investment + holding.get('pl', 0)
                quantity = holding.get('quantity', 0)

                if symbol not in prev_close_cache:
                    prev_close, prev_date = get_prev_trading_close_fyers(symbol)
                    prev_close_cache[symbol] = prev_close
                else:
                    prev_close = prev_close_cache[symbol]

                today_pnl = 0
                today_perc = 0
                if prev_close is not None and quantity > 0:
                    today_pnl = (ltp - prev_close) * quantity
                    total_today_pnl += today_pnl
                    today_perc = ((ltp - prev_close) / prev_close) * 100 if prev_close != 0 else 0

                row = [
                    symbol,
                    holding.get('pl', 0),
                    round(pl_percent, 2),
                    quantity,
                    holding.get('costPrice', 0),
                    ltp,
                    round(today_perc, 2) if prev_close is not None else "N/A",
                    investment,
                    current_value,
                    prev_close if prev_close is not None else "N/A",
                    round(today_pnl, 2)
                ]
                holdings_table.append(row)

            df_holdings = pd.DataFrame(holdings_table, columns=holdings_headers)
            st.dataframe(df_holdings, use_container_width=True)

            # --- Overall Summary ---
            st.subheader("Overall Summary")
            overall_table = [
                ["Total Investment", overall_data.get('total_investment', 0)],
                ["Total Current Value", overall_data.get('total_current_value', 0)],
                ["Overall P&L", overall_data.get('total_pl', 0)],
                ["Today's P&L", total_today_pnl]
            ]
            st.table(pd.DataFrame(overall_table, columns=["Metric", "Value"]))
        else:
            st.info("No holdings data available.")
    else:
        st.error(f"Error fetching holdings: {holdings.get('message', 'No message available')}")

    # --- Positions Section ---
    positions = fyers.positions()
    if positions['code'] == 200:
        positions_data = positions.get('netPositions', [])
        if positions_data:
            st.subheader("Positions")
            positions_table = []
            positions_headers = ["Symbol", "Net Qty", "Buy Qty", "Sell Qty", "Buy Avg", "Sell Avg", "LTP", "Realized P&L", "Unrealized P&L"]
            for position in sorted(positions_data, key=lambda x: x.get('symbol', '')):
                if position.get('realizedPL', 0) != 0 or position.get('unrealizedPL', 0) != 0:
                    row = [
                        position.get('symbol', ''),
                        position.get('netQty', 0),
                        position.get('buyQty', 0),
                        position.get('sellQty', 0),
                        position.get('buyAvg', 0),
                        position.get('sellAvg', 0),
                        position.get('ltp', 0),
                        position.get('realizedPL', 0),
                        position.get('unrealizedPL', 0)
                    ]
                    positions_table.append(row)
            if positions_table:
                df_positions = pd.DataFrame(positions_table, columns=positions_headers)
                st.dataframe(df_positions, use_container_width=True)
            else:
                st.info("No active positions.")
        else:
            st.info("No positions data available.")
    else:
        st.error(f"Error fetching positions: {positions.get('message', 'No message available')}")

    # --- Funds Section ---
    funds = fyers.funds()
    if funds['code'] == 200:
        funds_data = funds.get('fund_limit', [])
        if funds_data:
            st.subheader("Available Funds")
            funds_table = [
                ["Available Funds", funds_data[0].get('availableFunds', 0)],
                ["Used Margin", funds_data[0].get('usedMargin', 0)],
                ["Net Funds", funds_data[0].get('netFunds', 0)],
                ["Total Collateral", funds_data[0].get('totalCollateral', 0)]
            ]
            st.table(pd.DataFrame(funds_table, columns=["Metric", "Value"]))
        else:
            st.info("No funds data available.")
    else:
        st.error(f"Error fetching funds: {funds.get('message', 'No message available')}")

    st.session_state['refresh'] = False