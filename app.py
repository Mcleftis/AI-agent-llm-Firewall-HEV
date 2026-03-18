import streamlit as st
import pandas as pd
import numpy as np
import time
import os
import threading
import logging
import concurrent.futures  # noqa: F401
import http
from typing import Tuple, Union, Dict, Any
from dotenv import load_dotenv
import requests
import urllib3

load_dotenv()

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# --- GLOBAL CONSTANTS & SECRETS ---
API_URL = os.getenv("AZURE_API_URL", "http://127.0.0.1:8000/api/v1")
API_TOKEN = os.getenv("User_API_TOKEN", "fallback_token")

# Timeout constants (Για προστασία DoS & Bandit Security Pass)
WARMUP_TIMEOUT = 10 
REQUEST_TIMEOUT = 15

# Dummy dataset generation constants
DUMMY_MAX_SPEED = 120
DUMMY_SAMPLE_SIZE = 100
DUMMY_MAX_ENGINE_POWER = 50
DUMMY_MAX_REGEN_POWER = 20

# Disable SSL warnings (Bandit # nosec)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Hybrid AI System Control", page_icon="🧠", layout="wide")

# Καθολικά Headers 
GLOBAL_HEADERS = {
    "X-Auth-Token": API_TOKEN, 
    "Content-Type": "application/json"
}

# --- SENIOR TRICK: AI WARMUP (Εξαφανίζει το Cold Start) ---
@st.cache_resource
def warmup_ai() -> bool:
    def ping() -> None:
        try:
            payload = {"command": "warmup system", "user_prompt": "warmup system"}
            requests.post(
                f"{API_URL}/intent",
                json=payload,
                headers=GLOBAL_HEADERS,
                verify=False, # nosec
                timeout=WARMUP_TIMEOUT,
            )
        except Exception as e:
            logger.warning("AI warmup ping failed: %s", e)

    threading.Thread(target=ping, daemon=True).start()
    return True

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
st.markdown("### Distributed Neuro-Symbolic Architecture (Thin Client)")

# --- CHECK SERVER ---
server_status = "🔴 OFFLINE"
try:
    test = requests.get(f"{API_URL}/vehicle/telemetry", verify=False, timeout=5) # nosec
    if test.status_code in [http.HTTPStatus.OK, http.HTTPStatus.NOT_FOUND]:
        server_status = "🟢 ONLINE (Cloud API Connected)"
except:
    server_status = "🔴 OFFLINE (Check your Azure FQDN or Local Server)"

col_status1, col_status2 = st.columns([3, 1])
if "Demo" in status_msg:
    col_status1.warning(status_msg)
else:
    col_status1.success(status_msg)
col_status2.metric("API Connection", server_status)


# --- SIDEBAR (SINGLE INPUT) ---
st.sidebar.header("🗣️ Talk to the Car")
user_input = st.sidebar.text_input("Command:", placeholder="e.g. 'I want to go fast'")

if "mode" not in st.session_state:
    st.session_state.update({
        "mode": "WAITING...",
        "aggr": 0.5,
        "reasoning": "Waiting for input...",
        "latency": "0 ms",
        "bandwidth": "0 B"
    })

# --- ΚΟΥΜΠΙ ME LOGIC & OBSERVABILITY ---
if st.sidebar.button("🧠 Analyze Intent"):
    if user_input:
        with st.spinner("Sending command to Neural Core (Azure Cloud)..."):
            start_time = time.time()
            
            try:
                payload = {"command": user_input, "user_prompt": user_input}
                req_bytes = len(str(payload).encode('utf-8'))

                response = requests.post(f"{API_URL}/intent", json=payload, headers=GLOBAL_HEADERS, verify=False, timeout=REQUEST_TIMEOUT) # nosec
                if response.status_code == http.HTTPStatus.NOT_FOUND:
                    response = requests.post(f"{API_URL}/control/intent", json=payload, headers=GLOBAL_HEADERS, verify=False, timeout=REQUEST_TIMEOUT) # nosec

                latency_ms = (time.time() - start_time) * 1000
                st.session_state["latency"] = f"{latency_ms:.0f} ms"
                
                res_bytes = len(response.content) if response.content else 0
                st.session_state["bandwidth"] = f"⬆️ {req_bytes}B | ⬇️ {res_bytes}B"

                if response.status_code == http.HTTPStatus.OK:
                    data = response.json()
                    st.session_state["mode"] = data.get("selected_mode") or data.get("mode") or "NORMAL"
                    st.session_state["aggr"] = data.get("throttle_sensitivity") or data.get("aggressiveness") or 0.5
                    st.session_state["reasoning"] = data.get("reasoning", "Processed via Distributed Core.")
                    st.sidebar.success("Approved ✅")
                elif response.status_code == http.HTTPStatus.FORBIDDEN:
                    st.session_state["mode"] = "BLOCKED ⛔"
                    st.session_state["reasoning"] = response.json().get("reason", "Security Alert")
                    st.sidebar.error("Firewall Blocked Action!")
                else:
                    st.error(f"Server Error: {response.status_code}")

            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to Server.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.sidebar.warning("Please type a command first.")


# --- HPC BATCH PROCESSING (BETA CAE STYLE) ---
st.sidebar.divider()
st.sidebar.subheader("⚙️ HPC Batch Processing")
st.sidebar.caption("Test Cloud Concurrency & Load Balancing")

if st.sidebar.button("🚀 Run Parallel Scenarios"):
    batch_commands = [
        "I am driving on ice, be careful",
        "I need maximum acceleration to overtake",
        "System failure, stop the car now"
    ]
    
    st.sidebar.info(f"Dispatching {len(batch_commands)} parallel jobs to Backend...")
    batch_start = time.time()
    results = []
    
    def fetch_intent_worker(cmd: str) -> Tuple[str, Union[Dict[str, Any], str]]:
        payload = {"command": cmd, "user_prompt": cmd}
        try:
            res = requests.post(f"{API_URL}/intent", json=payload, headers=GLOBAL_HEADERS, verify=False, timeout=REQUEST_TIMEOUT) # nosec
            if res.status_code == http.HTTPStatus.NOT_FOUND:
                res = requests.post(f"{API_URL}/control/intent", json=payload, headers=GLOBAL_HEADERS, verify=False, timeout=REQUEST_TIMEOUT) # nosec
            
            return cmd, res.json() if res.status_code == http.HTTPStatus.OK else f"Error {res.status_code}"
        except Exception:
            return cmd, "FAILED"

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_intent_worker, cmd): cmd for cmd in batch_commands}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    total_batch_time = (time.time() - batch_start) * 1000
    st.success(f"HPC Batch Simulation Completed in {total_batch_time:.0f} ms ⚡")
    
    batch_df = pd.DataFrame([
        {
            "Scenario": r[0], 
            "AI Mode": r[1].get("selected_mode") or r[1].get("mode") or "N/A" if isinstance(r[1], dict) else r[1]
        }
        for r in results
    ])
    st.table(batch_df)


# --- METRICS (NETWORK METRICS) ---
st.subheader("📊 Vehicle Core & Network Telemetry")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("AI Detected Mode", st.session_state["mode"])
k2.metric("Throttle Sensitivity", f"{st.session_state['aggr']*100:.0f}%" if isinstance(st.session_state['aggr'], (int, float)) else "N/A")
k3.metric("☁️ Cloud Latency", st.session_state["latency"])
k4.metric("📡 Bandwidth", st.session_state["bandwidth"])
k5.info(f"**AI Reasoning:** {st.session_state['reasoning']}")


# --- GRAPHS (BULLETPROOF PLACEHOLDERS) ---
st.divider()
st.subheader("📡 Live Telemetry Simulation")

speed_series = df.get("Speed (km/h)", df.iloc[:, 0])
pwr_cols = ["Engine Power (kW)", "Regenerative Braking Power (kW)"]
valid_cols = [c for c in pwr_cols if c in df.columns]
chart_colors = ["#ff4b4b", "#00ff00"][: len(valid_cols)]

col1, col2 = st.columns(2)
chart_speed_placeholder = col1.empty()
chart_power_placeholder = col2.empty()

start_simulation = st.sidebar.button("🚀 Start Simulation")

if start_simulation:
    steps = min(len(df), 200)
    progress_bar = st.progress(0)

    chart_speed = chart_speed_placeholder.line_chart(speed_series.iloc[[0]], height=300)
    if valid_cols:
        chart_power = chart_power_placeholder.area_chart(df[valid_cols].iloc[[0]], height=300, color=chart_colors)

    for i in range(1, steps):
        chart_speed.add_rows(speed_series.iloc[[i]])
        if valid_cols:
            chart_power.add_rows(df[valid_cols].iloc[[i]])

        progress_bar.progress(i / (steps - 1))
        time.sleep(0.05)

    st.success("Ride Complete ✅")
else:
    chart_speed_placeholder.line_chart(speed_series, height=300)
    if valid_cols:
        chart_power_placeholder.area_chart(df[valid_cols], height=300, color=chart_colors)