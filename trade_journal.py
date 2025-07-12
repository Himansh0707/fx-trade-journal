import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pytz
import os

# -------------------- DB SETUP -------------------- #
DB_FILE = "trade_journal.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

# Create base table if not exists
c.execute('''CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair TEXT,
    trade_type TEXT,
    time TEXT,
    tp INTEGER,
    sl INTEGER,
    rr REAL,
    reason TEXT
)''')
conn.commit()

# Safely add missing columns
existing_cols = [row[1] for row in c.execute("PRAGMA table_info(trades)").fetchall()]

if "entry_price" not in existing_cols:
    c.execute("ALTER TABLE trades ADD COLUMN entry_price REAL")
if "result" not in existing_cols:
    c.execute("ALTER TABLE trades ADD COLUMN result TEXT")
if "pips" not in existing_cols:
    c.execute("ALTER TABLE trades ADD COLUMN pips INTEGER")
conn.commit()

# -------------------- FUNCTIONS -------------------- #
def insert_trade(pair, trade_type, time, entry_price, tp, sl, rr, result, pips, reason):
    c.execute("""
        INSERT INTO trades (pair, trade_type, time, entry_price, tp, sl, rr, result, pips, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pair, trade_type, time, entry_price, tp, sl, rr, result, pips, reason))
    conn.commit()

def get_all_trades():
    return pd.read_sql("SELECT * FROM trades", conn)

def delete_trade(trade_id):
    c.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()

def update_result_pips(trade_id, result, pips):
    c.execute("UPDATE trades SET result = ?, pips = ? WHERE id = ?", (result, pips, trade_id))
    conn.commit()

# -------------------- UI CONFIG -------------------- #
st.set_page_config(page_title="📘 FX Trade Journal", layout="wide")
st.title("📘 My Trade Journal")
st.markdown("---")

# -------------------- DARK MODE TOGGLE -------------------- #
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = True

theme = "dark" if st.session_state.dark_mode else "light"

if st.button("🌗 Toggle Theme"):
    st.session_state.dark_mode = not st.session_state.dark_mode
    st.rerun()

# -------------------- TRADE ENTRY FORM -------------------- #
st.subheader("➕ Add New Trade")
with st.form("trade_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        pair = st.selectbox("Select Pair", ["USDJPY", "EURUSD", "GBPUSD", "XAUUSD"])
        trade_type = st.radio("Trade Type", ["Buy", "Sell"], horizontal=True)
        entry_price = st.number_input("Entry Price", step=0.01)
    with col2:
        tp = st.number_input("Take Profit (Points)", step=1)
        sl = st.number_input("Stop Loss (Points)", step=1)
        result = st.selectbox("Result (Optional)", ["", "Win", "Loss", "Breakeven"])
        pips = st.number_input("Pips Gained/Lost (Optional)", step=1, value=0)
    with col3:
        reason = st.text_area("Reason for Trade", height=100)

    submitted = st.form_submit_button("💾 Save Trade")

    if submitted:
        if tp > 0 and sl > 0 and entry_price > 0:
            rr = round(tp / sl, 2)
            india_time = datetime.now(pytz.timezone("Asia/Kolkata"))
            insert_trade(pair, trade_type, india_time.strftime("%Y-%m-%d %H:%M:%S"), entry_price, tp, sl, rr, result or None, pips or None, reason)
            st.success("✅ Trade saved successfully!")
        else:
            st.error("❌ TP, SL, and Entry Price must be greater than 0")

# -------------------- FILTERS -------------------- #
st.markdown("---")
st.subheader("🔍 Filter Trades")
all_trades = get_all_trades()

colf1, colf2, colf3 = st.columns(3)
with colf1:
    pair_filter = st.multiselect("Filter by Pair", options=all_trades["pair"].unique(), default=all_trades["pair"].unique())
with colf2:
    type_filter = st.multiselect("Filter by Trade Type", options=["Buy", "Sell"], default=["Buy", "Sell"])
with colf3:
    date_filter = st.date_input("Filter by Date (From)", value=datetime(2025, 1, 1))

filtered = all_trades[(all_trades["pair"].isin(pair_filter)) &
                      (all_trades["trade_type"].isin(type_filter)) &
                      (pd.to_datetime(all_trades["time"]) >= pd.to_datetime(date_filter))]

# -------------------- DISPLAY DATA -------------------- #
st.markdown("---")
st.subheader("📊 Trade History")

def color_trade_type(val):
    color = "green" if val == "Buy" else "red"
    return f"color: {color}; font-weight: bold"

if not filtered.empty:
    styled_table = filtered.style.applymap(color_trade_type, subset=["trade_type"])
    st.dataframe(styled_table, use_container_width=True, height=450)

    with st.expander("✏️ Update Result/Pips"):
        update_id = st.number_input("Trade ID to update", step=1)
        result_update = st.selectbox("Update Result", ["Win", "Loss", "Breakeven"])
        pips_update = st.number_input("Update Pips", step=1)
        if st.button("✅ Update Trade"):
            update_result_pips(update_id, result_update, pips_update)
            st.success("Trade updated!")
            st.rerun()

    with st.expander("🗑️ Delete a Trade"):
        delete_id = st.number_input("Enter Trade ID to Delete", step=1)
        if st.button("❌ Delete Trade"):
            delete_trade(delete_id)
            st.warning("Trade deleted!")
            st.rerun()
else:
    st.info("No trades found for selected filters.")

# -------------------- EXPORT BUTTON -------------------- #
st.markdown("---")
st.download_button("⬇️ Download CSV", data=filtered.to_csv(index=False).encode('utf-8'), file_name="trade_journal.csv", mime="text/csv")

# -------------------- WEEKLY/MONTHLY STATS -------------------- #
st.markdown("---")
st.subheader("📈 Weekly & Monthly Stats")

if not all_trades.empty:
    all_trades["time"] = pd.to_datetime(all_trades["time"])
    all_trades["week"] = all_trades["time"].dt.isocalendar().week
    all_trades["month"] = all_trades["time"].dt.month

    colw1, colw2 = st.columns(2)
    with colw1:
        st.write("**Weekly Trade Count**")
        weekly = all_trades.groupby("week").size()
        st.bar_chart(weekly)
    with colw2:
        st.write("**Monthly Trade Count**")
        monthly = all_trades.groupby("month").size()
        st.bar_chart(monthly)
else:
    st.info("No data to show stats.")
