import streamlit as st
import pandas as pd
import numpy as np
import time
import os
from dotenv import load_dotenv
load_dotenv()
import requests
import urllib3

# Ρυθμίσεις Σύνδεσης με τον Server
API_URL = "http://127.0.0.1:5000/api/v1" # Γύρισα σε HTTP αν δεν έχεις πιστοποιητικά. Αν έχεις βάλτο https.
API_TOKEN = os.getenv("User_API_TOKEN", "fallback_token")

# Απενεργοποίηση warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="Hybrid AI System Control", page_icon="🧠", layout="wide")

# --- DATASET LOADING ---
@st.cache_data
def get_dataset():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_paths = [
        os.path.join(base_dir, "data", "my_working_dataset.csv"),
        os.path.join(base_dir, "my_working_dataset.csv"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            df = pd.read_csv(path)
            df.columns = [c.strip() for c in df.columns]
            cols_to_fix = ["Engine Power (kW)", "Regenerative Braking Power (kW)"]
            for col in cols_to_fix:
                if col in df.columns: df[col] = df[col].fillna(0)
            return df, "✅ Data Loaded"
            
    dummy_df = pd.DataFrame({
        "Speed (km/h)": np.random.uniform(0, 120, 100),
        "Engine Power (kW)": np.random.uniform(0, 50, 100),
        "Regenerative Braking Power (kW)": np.random.uniform(0, 20, 100),
    })
    return dummy_df, "⚠️ Demo Data Mode"

df, status_msg = get_dataset()

#header
st.title("🧠 True Semantic AI Control")
st.markdown("### Powered by Flask API & Streamlit")

#Check Server
server_status = "🔴 OFFLINE"
try:
    test = requests.get(f"{API_URL}/vehicle/telemetry", verify=False , timeout=2)
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

#Sidebar
st.sidebar.header("🗣️ Talk to the Car")
user_input = st.sidebar.text_input("Command:", placeholder="e.g. 'I want to go fast' or 'DROP TABLE users'")

if 'mode' not in st.session_state:
    st.session_state['mode'] = "WAITING..."
    st.session_state['aggr'] = 0.5
    st.session_state['reasoning'] = "Waiting for input..."

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
                    timeout=120 # <--- ΑΛΛΑΞΕ ΤΟ ΣΕ 120 (2 λεπτά)
                )
                
                if response.status_code == 200:
                    data = response.json()
                    st.write("🔍 DEBUG RAW DATA:", data) 

                    st.session_state['mode'] = data.get('selected_mode', 'UNKNOWN')
                    st.session_state['aggr'] = data.get('throttle_sensitivity', 0.5)
                    st.session_state['reasoning'] = data.get('reasoning', 'No reasoning provided.')
                    st.sidebar.success("Approved ✅")
                
                elif response.status_code == 403:
                    st.session_state['mode'] = "BLOCKED ⛔"
                    st.session_state['reasoning'] = response.json().get('reason', 'Security Alert')
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
mode = st.session_state['mode']
aggressiveness = st.session_state['aggr']
reasoning = st.session_state['reasoning']

k1, k2, k3 = st.columns(3)
k1.metric("AI Detected Mode", mode)
k2.metric("Throttle Sensitivity", f"{aggressiveness*100:.0f}%")
k3.info(f"💡 **AI Reasoning:** {reasoning}")

# --- GRAPHS ---
st.divider()
st.subheader("📡 Live Telemetry Simulation")
col1, col2 = st.columns(2)
chart_speed = col1.empty()
chart_power = col2.empty()

start_simulation = st.sidebar.button("🚀 Start Simulation")

if start_simulation:
    steps = min(len(df), 200)
    progress_bar = st.progress(0)
    
    for i in range(1, steps):
        current_data = df.iloc[:i]
        chart_speed.line_chart(current_data.get("Speed (km/h)", current_data.iloc[:, 0]), height=300)
        
        pwr_cols = ["Engine Power (kW)", "Regenerative Braking Power (kW)"]
        valid_cols = [c for c in pwr_cols if c in df.columns]
        if valid_cols:
            chart_power.area_chart(current_data[valid_cols], height=300, color=["#ff4b4b", "#00ff00"])
            
        progress_bar.progress(i/steps)
        time.sleep(0.05)
        
    st.success("Ride Complete ✅")
else:
    chart_speed.line_chart(df.get("Speed (km/h)", df.iloc[:, 0]), height=300)
    pwr_cols = ["Engine Power (kW)", "Regenerative Braking Power (kW)"]
    valid_cols = [c for c in pwr_cols if c in df.columns]
    if valid_cols:
        chart_power.area_chart(df[valid_cols], height=300, color=["#ff4b4b", "#00ff00"])