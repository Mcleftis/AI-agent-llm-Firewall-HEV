import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import threading
import logging
from dotenv import load_dotenv
import requests
import urllib3

load_dotenv()

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# --- GLOBAL CONSTANTS ---
# Connection settings
API_URL = "http://127.0.0.1:5000/api/v1"
API_TOKEN = os.getenv("User_API_TOKEN", "fallback_token")

# Timeout constants
WARMUP_TIMEOUT = 30

# Dummy dataset generation constants
DUMMY_MAX_SPEED = 120
DUMMY_SAMPLE_SIZE = 100
DUMMY_MAX_ENGINE_POWER = 50
DUMMY_MAX_REGEN_POWER = 20

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Hybrid AI System Control", page_icon="🧠", layout="wide")


# --- SENIOR TRICK: AI WARMUP (Εξαφανίζει το Cold Start) ---
@st.cache_resource
def warmup_ai() -> bool:
    """Στέλνει ένα αθόρυβο request στο background για να φορτώσει το μοντέλο στη VRAM"""

    def ping() -> None:
        try:
            requests.post(
                f"{API_URL}/control/intent",
                json={"command": "warmup system"},
                headers={"X-Auth-Token": API_TOKEN, "Content-Type": "application/json"},
                verify=False,
                timeout=WARMUP_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            logger.warning("AI warmup ping failed: %s", e)

    threading.Thread(target=ping, daemon=True).start()
    return True


# Ξυπνάμε το AI με το που ανοίγει η σελίδα!
warmup_ai()


# --- DATASET LOADING ---
@st.cache_data
def get_dataset() -> tuple[pd.DataFrame, str]:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(base_dir, "data", "my_working_dataset.csv"),
        os.path.join(base_dir, "my_working_dataset.csv"),
    ]

    for path in possible_paths:
        if not os.path.exists(path):
            continue

        telemetry_data = pd.read_csv(path)
        telemetry_data.columns = [c.strip() for c in telemetry_data.columns]

        cols_to_fix = ["Engine Power (kW)", "Regenerative Braking Power (kW)"]
        for col in cols_to_fix:
            if col in telemetry_data.columns:
                telemetry_data[col] = telemetry_data[col].fillna(0)

        return telemetry_data, "✅ Data Loaded"

    telemetry_data = pd.DataFrame(
        {
            "Speed (km/h)": np.random.uniform(0, DUMMY_MAX_SPEED, DUMMY_SAMPLE_SIZE),
            "Engine Power (kW)": np.random.uniform(0, DUMMY_MAX_ENGINE_POWER, DUMMY_SAMPLE_SIZE),
            "Regenerative Braking Power (kW)": np.random.uniform(0, DUMMY_MAX_REGEN_POWER, DUMMY_SAMPLE_SIZE),
        }
    )
    return telemetry_data, "⚠️ Demo Data Mode"


df, status_msg = get_dataset()

# --- HEADER ---
st.title("🧠 True Semantic AI Control")
st.markdown("### Powered by Flask API & Streamlit")

# --- CHECK SERVER ---
server_status = "🔴 OFFLINE"
try:
    test = requests.get(f"{API_URL}/vehicle/telemetry", verify=False, timeout=2)
    if test.status_code == 200:
        server_status = "🟢 ONLINE (API Connected)"
except:
    server_status = "🔴 OFFLINE (Run server.py first!)"

col_status1, col_status2 = st.columns([3, 1])
if "Demo" in status_msg:
    col_status1.warning(status_msg)
else:
    col_status1.success(status_msg)
col_status2.metric("API Connection", server_status)

# --- SIDEBAR ---
st.sidebar.header("🗣️ Talk to the Car")
user_input = st.sidebar.text_input("Command:", placeholder="e.g. 'I want to go fast' or 'DROP TABLE users'")

if "mode" not in st.session_state:
    st.session_state["mode"] = "WAITING..."
    st.session_state["aggr"] = 0.5
    st.session_state["reasoning"] = "Waiting for input..."

# --- ΚΟΥΜΠΙ ME LOGIC & DEBUG ---
if st.sidebar.button("🧠 Analyze Intent"):
    if user_input:
        with st.spinner("Sending command to Neural Core (Server)..."):
            try:
                payload = {"command": user_input}
                headers = {"X-Auth-Token": API_TOKEN, "Content-Type": "application/json"}

                response = requests.post(
                    f"{API_URL}/control/intent",
                    json=payload,
                    headers=headers,
                    verify=False,
                    timeout=120,
                )

                if response.status_code == 200:
                    data = response.json()
                    st.session_state["mode"] = data.get("selected_mode", "UNKNOWN")
                    st.session_state["aggr"] = data.get("throttle_sensitivity", 0.5)
                    st.session_state["reasoning"] = data.get("reasoning", "No reasoning provided.")
                    st.sidebar.success("Approved ✅")

                elif response.status_code == 403:
                    st.session_state["mode"] = "BLOCKED ⛔"
                    st.session_state["reasoning"] = response.json().get("reason", "Security Alert")
                    st.sidebar.error("Firewall Blocked Action!")

                else:
                    st.error(f"Server Error: {response.status_code}")

            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to Server. Is server.py running?")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.sidebar.warning("Please type a command first.")

# --- METRICS ---
mode = st.session_state["mode"]
aggressiveness = st.session_state["aggr"]
reasoning = st.session_state["reasoning"]

k1, k2, k3 = st.columns(3)
k1.metric("AI Detected Mode", mode)
k2.metric("Throttle Sensitivity", f"{aggressiveness*100:.0f}%")
k3.info(f" **AI Reasoning:** {reasoning}")

# --- GRAPHS (BULLETPROOF PLACEHOLDERS) ---
st.divider()
st.subheader("📡 Live Telemetry Simulation")

# 1. PRE-CALCULATION
speed_series = df.get("Speed (km/h)", df.iloc[:, 0])
pwr_cols = ["Engine Power (kW)", "Regenerative Braking Power (kW)"]
valid_cols = [c for c in pwr_cols if c in df.columns]
chart_colors = ["#ff4b4b", "#00ff00"][: len(valid_cols)]

# 2. PLACEHOLDERS (ΑΥΤΟ ΛΥΝΕΙ ΤΟ ΔΙΠΛΟ ΓΡΑΦΗΜΑ!)
col1, col2 = st.columns(2)
chart_speed_placeholder = col1.empty()
chart_power_placeholder = col2.empty()

start_simulation = st.sidebar.button("🚀 Start Simulation")

if start_simulation:
    steps = min(len(df), 200)
    progress_bar = st.progress(0)

    # Αρχικοποίηση στα placeholders
    chart_speed = chart_speed_placeholder.line_chart(speed_series.iloc[[0]], height=300)
    if valid_cols:
        chart_power = chart_power_placeholder.area_chart(df[valid_cols].iloc[[0]], height=300, color=chart_colors)

    # Streaming
    for i in range(1, steps):
        new_speed = speed_series.iloc[[i]]
        chart_speed.add_rows(new_speed)

        if valid_cols:
            new_power = df[valid_cols].iloc[[i]]
            chart_power.add_rows(new_power)

        progress_bar.progress(i / (steps - 1))
        time.sleep(0.05)

    st.success("Ride Complete ✅")
else:
    # Static View (Γράφει ΠΑΝΩ στα placeholders, οπότε δεν διπλασιάζει ποτέ)
    chart_speed_placeholder.line_chart(speed_series, height=300)
    if valid_cols:
        chart_power_placeholder.area_chart(df[valid_cols], height=300, color=chart_colors)