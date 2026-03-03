import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
import ollama
import json
import time
import re
import os
import ctypes
from typing import Dict, Any, Optional
import torch  # ΝΕΟ: Απαραίτητο για να ελέγξουμε τη GPU!

DATA_FILENAME = "data/my_working_dataset.csv"
MODEL_PATH = "models/ppo_hev"
OLLAMA_HOST = "http://127.0.0.1:11434"
LLM_MODEL = "llama3.2:1b" # Το γρήγορο, τοπικό μοντέλο

# --- 🚀 ΦΟΡΤΩΣΗ C++ ΜΗΧΑΝΗΣ ΦΥΣΙΚΗΣ (ΤΡΕΧΕΙ ΣΤΗ CPU) ---
CPP_AVAILABLE = False
try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_path = os.path.join(base_dir, "cpp_core_physics_engine", "physics.dll")
    physics_lib = ctypes.CDLL(lib_path)
    
    # 1. Επιτάχυνση
    physics_lib.calculate_acceleration.restype = ctypes.c_float
    physics_lib.calculate_acceleration.argtypes = [
        ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float
    ]
    
    # 2. Μπαταρία
    physics_lib.solve_battery_thermal_dynamics.restype = None 
    physics_lib.solve_battery_thermal_dynamics.argtypes = [
        ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)
    ]

    # 3. Monte Carlo Safety Check
    physics_lib.run_monte_carlo_safety_check.restype = ctypes.c_float
    physics_lib.run_monte_carlo_safety_check.argtypes = [
        ctypes.c_float, ctypes.c_float, ctypes.c_int
    ]
    
    CPP_AVAILABLE = True
    print("🚀 [SYSTEM] C++ Physics & Monte Carlo Engine Loaded Successfully (CPU/OpenMP)!")
except Exception as e:
    print(f"⚠️ [SYSTEM] C++ Engine missing or failed ({e}). Using Python Fallback.")

# --- ΦΟΡΤΩΣΗ ΜΟΝΤΕΛΩΝ ΣΤΗ ΜΝΗΜΗ (PPO ΣΤΗ GPU, LLM ΣΤΗ GPU) ---
print("[MEMORY] Pre-loading AI Models into RAM/VRAM...")
GLOBAL_OLLAMA_CLIENT = ollama.Client(host=OLLAMA_HOST)
GLOBAL_PPO_MODEL = None

try:
    if os.path.exists(MODEL_PATH) or os.path.exists(MODEL_PATH + ".zip"):
        
        # --- ΤΟ ΜΑΓΙΚΟ ΚΟΛΠΟ ΓΙΑ ΤΗ GPU ---
        # Ελέγχει αν το σύστημα έχει κάρτα γραφικών Nvidia (CUDA) 
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 [SYSTEM] PyTorch Backend selected: {device.upper()}")
        
        # Φορτώνει το AI απευθείας στη VRAM της κάρτας!
        GLOBAL_PPO_MODEL = PPO.load(MODEL_PATH, device=device)
        print("[MEMORY] PPO Model Loaded Successfully (Hardware Accelerated).")
except Exception as e:
    print(f"⚠️ [MEMORY] PPO Load Failed: {e}")


class DigitalTwinEnv(gym.Env):
    def __init__(self, df):
        super(DigitalTwinEnv, self).__init__()
        self.df = df
        self.current_step = 0
        self.mass = 1600.0       
        self.max_power = 200.0   
        self.gravity = 9.81      
        self.air_drag_coeff = 0.3 
        self.dt = 1.0            
        self.current_speed_ms = 0.0 
        self.soc = 80.0          
        self.temperature = 25.0  
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.current_speed_ms = 0.0 
        self.soc = 80.0
        self.temperature = 25.0
        return self._get_obs(), {}

    def _get_obs(self):
        speed_kmh = self.current_speed_ms * 3.6
        noisy_speed = speed_kmh + np.random.normal(0, 0.5)
        noisy_speed = max(0.0, noisy_speed)
        
        dist = 100.0
        if self.current_step < len(self.df):
            if 'Distance' in self.df.columns:
                dist = self.df.iloc[self.current_step]['Distance']

        return np.array([noisy_speed, 0.0, dist, self.soc], dtype=np.float32)

    def step(self, action):
        time.sleep(0.01) 
        throttle = float(action[0])
        slope_deg = 0.0
        
        if self.current_step < len(self.df):
            if 'Slope' in self.df.columns:
                slope_deg = self.df.iloc[self.current_step]['Slope']

        monte_carlo_risk = 0.0 

        # -------- Η C++ ΜΗΧΑΝΗ ΦΥΣΙΚΗΣ --------
        if CPP_AVAILABLE:
            
            # 1. MONTE CARLO SAFETY CHECK
            monte_carlo_risk = physics_lib.run_monte_carlo_safety_check(
                ctypes.c_float(self.current_speed_ms), 
                ctypes.c_float(throttle), 
                ctypes.c_int(10000)
            )
            
            if monte_carlo_risk > 0.05:
                throttle = 0.0 

            # 2. Υπολογισμός Επιτάχυνσης (Native)
            acceleration = physics_lib.calculate_acceleration(
                throttle, self.current_speed_ms, self.mass, self.air_drag_coeff, slope_deg
            )
            
            # 3. Υπολογισμός Μπαταρίας με Pointers (Native)
            power_output_kw = throttle * self.max_power
            current_amps = (power_output_kw * 1000.0) / 400.0 
            
            c_soc = ctypes.c_float(self.soc)
            c_temp = ctypes.c_float(self.temperature)
            
            physics_lib.solve_battery_thermal_dynamics(
                ctypes.c_float(current_amps),
                ctypes.c_float(self.dt),
                ctypes.byref(c_soc),
                ctypes.byref(c_temp)
            )
            
            self.soc = np.clip(float(c_soc.value), 0, 100)
            self.temperature = float(c_temp.value)
            energy_used_kwh = power_output_kw * (self.dt / 3600.0) 
            
        else:
            # -------- PYTHON FALLBACK --------
            power_output_kw = throttle * self.max_power
            force_propulsion = (power_output_kw * 1000.0) / (self.current_speed_ms + 1.0)
            force_gravity = self.mass * self.gravity * np.sin(np.radians(slope_deg))
            force_drag = 0.5 * self.air_drag_coeff * (self.current_speed_ms ** 2)
            net_force = force_propulsion - (force_gravity + force_drag)
            acceleration = net_force / self.mass
            
            energy_used_kwh = power_output_kw * (self.dt / 3600.0)
            self.soc -= energy_used_kwh * 2.0 
            self.soc = np.clip(self.soc, 0, 100)
            # ---------------------------------------------------

        # Ενημέρωση ταχύτητας
        self.current_speed_ms += acceleration * self.dt
        if self.current_speed_ms < 0: self.current_speed_ms = 0
        
        self.current_step += 1
        terminated = self.current_step >= len(self.df) - 1
        
        info = {
            "real_speed_kmh": self.current_speed_ms * 3.6,
            "fuel": energy_used_kwh, 
            "soc": self.soc,
            "temp_celsius": self.temperature,
            "mc_risk_factor": monte_carlo_risk 
        }
        
        return self._get_obs(), 0.0, terminated, False, info


def get_driver_intent(forced_prompt: Optional[str] = None) -> Dict[str, Any]:
    print("\n" + "="*60)
    print("🧠 NEURO-SYMBOLIC ENGINE: SEMANTIC ANALYSIS STARTED")
    print("="*60)
    
    user_command = forced_prompt if forced_prompt else "Drive normally"
    
    system_prompt = """
    You are the AI Control Unit of a VEHICLE SIMULATOR.
    Evaluate the user command and map it to an 'urgency_score' from 0 to 10.
    (0 = stop/emergency, 5 = normal driving, 10 = maximum speed/aggressive).
    Schema required: {"urgency_score": 10, "reasoning": "User wants to go fast"}
    """
    
    params = {"mode": "NORMAL", "aggressiveness": 0.5, "reasoning": "System Initialized"}

    try:
        response = GLOBAL_OLLAMA_CLIENT.chat(
            model=LLM_MODEL, 
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_command},
            ],
            format='json', # Η εντολή που αναγκάζει το AI να βγάζει ΜΟΝΟ JSON
            options={
                'temperature': 0.0, # Μηδενική παραισθησιογόνος δημιουργικότητα
                'num_predict': 100
            }
        )
        
        content = response['message']['content']
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            result = json.loads(json_match.group(0)) if json_match else {}

        score = int(result.get("urgency_score", 5))
        reason = str(result.get("reasoning", "Parsed default"))
        
        # --- SYMBOLIC GUARDRAILS ---
        cmd_lower = user_command.lower()
        danger_words = ["crash", "cliff", "kill", "die", "death", "ignore", "lights"]
        if any(word in cmd_lower for word in danger_words):
            score = 0 
            reason = "Symbolic Safety Layer Override: Illegal/Dangerous Command detected."
        elif any(word in cmd_lower for word in ["eco", "slow", "save battery"]):
            score = 2 
            reason = "Symbolic Guardrail: Eco Mode explicitly requested."

        if score >= 7:
            mode, aggressiveness = "SPORT", 1.0
        elif score <= 1: 
            mode, aggressiveness = "EMERGENCY_COAST", 0.0 
        elif score <= 3:
            mode, aggressiveness = "ECO", 0.2
        else:
            mode, aggressiveness = "NORMAL", float(score) / 10.0
            
        params = {"mode": mode, "aggressiveness": aggressiveness, "reasoning": reason}

    except Exception as e:
        print(f"[SYSTEM ERROR] LLM Logic Failed: {e}")
        params = {"mode": "NORMAL", "aggressiveness": 0.5, "reasoning": f"Fallback due to Error: {e}"}
        
    return params

def run_live_system(prompt: Optional[str] = None, model_path: str = MODEL_PATH):
    pass # Main loop delegated to app.py/server.py

if __name__ == "__main__":
    run_live_system()