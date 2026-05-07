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
from typing import Dict, Any, Optional, Tuple
import torch


# =============================================================================
# CONSTANTS  (No Magic Numbers anywhere below this block)
# =============================================================================

# --- File paths ---
DATA_FILENAME   = "data/my_working_dataset.csv"
MODEL_PATH      = "models/ppo_hev"
OLLAMA_HOST     = "http://127.0.0.1:11434"
LLM_MODEL       = "llama3.2:1b"

# --- Vehicle physics defaults ---
DEFAULT_MASS_KG         = 1600.0
DEFAULT_MAX_POWER_KW    = 200.0
GRAVITY_MS2             = 9.81
DEFAULT_AIR_DRAG_COEFF  = 0.3
DEFAULT_DT_S            = 1.0
DEFAULT_SOC_PCT         = 80.0
DEFAULT_TEMP_C          = 25.0

# --- Observation / sensor ---
KMH_PER_MS              = 3.6
SPEED_NOISE_STD         = 0.5
DEFAULT_DISTANCE_M      = 100.0
OBS_SHAPE               = 4

# --- Physics engine ---
MONTE_CARLO_SAMPLES     = 10_000
MC_RISK_THRESHOLD       = 0.05
VOLTAGE_V               = 400.0
WATTS_PER_KW            = 1_000.0
SECONDS_PER_HOUR        = 3_600.0
SOC_DRAIN_FACTOR        = 2.0
SOC_MIN                 = 0.0
SOC_MAX                 = 100.0
STEP_SLEEP_S            = 0.01

# --- GPU/CPU DLL paths ---
USE_GPU      = True
GPU_DLL_PATH = './cpp_core_physics_engine/physics_gpu.dll'
CPU_DLL_PATH = './cpp_core_physics_engine/physics.dll'

# --- LLM / Neuro-Symbolic ---
SEPARATOR_WIDTH             = 60
LLM_MAX_TOKENS              = 100
LLM_TEMPERATURE             = 0.0
LLM_CONTEXT_RESET_DELAY_S   = 0.5      # ✅ FIX 1: Εξαγωγή του magic number 0.5
DEFAULT_URGENCY             = 5
DEFAULT_AGGRESSIVENESS      = 0.5

# Urgency thresholds
URGENCY_SPORT_MIN       = 7
URGENCY_ECO_MAX         = 3
URGENCY_EMERGENCY_MAX   = 1

# Aggressiveness per mode
AGG_SPORT               = 1.0
AGG_EMERGENCY           = 0.0
AGG_ECO                 = 0.2

# Guardrail override scores
URGENCY_ECO_SCORE       = 2
URGENCY_DANGER_SCORE    = 0

# Score normalisation
URGENCY_SCALE           = 10.0

# Physics exponents
DRAG_FORCE_EXPONENT     = 2

# Keyword lists
DANGER_WORDS = ["crash", "cliff", "kill", "die", "death", "ignore", "lights"]
ECO_WORDS    = ["eco", "slow", "save battery"]


# =============================================================================
# C++ STRUCT  (IPC / Zero-Copy Pointers)
# =============================================================================

class VehicleState(ctypes.Structure):
    _fields_ = [
        ("speed_ms",       ctypes.c_float),
        ("mass",           ctypes.c_float),
        ("air_drag_coeff", ctypes.c_float),
        ("slope_deg",      ctypes.c_float),
        ("soc",            ctypes.c_float),
        ("temperature",    ctypes.c_float),
    ]


# =============================================================================
# C++ ENGINE LOADER
# =============================================================================

# ✅ FIX: base_dir ορίζεται εδώ (module level) ώστε να είναι διαθέσιμο
#         τόσο στο Physics loader όσο και στο Firewall loader παρακάτω.
base_dir = os.path.dirname(os.path.abspath(__file__))

CPP_AVAILABLE = False
physics_lib   = None

try:
    # --- CUDA GPU INTEGRATION (Drop-In ABI Replacement) ---
    if USE_GPU and os.path.exists(GPU_DLL_PATH):
        print("🚀 [SYSTEM] GPU Detected! Loading CUDA Physics Engine...")
        physics_lib = ctypes.cdll.LoadLibrary(GPU_DLL_PATH)
    else:
        print("⚙️ [SYSTEM] Loading CPU Physics Engine (Fallback)...")
        physics_lib = ctypes.cdll.LoadLibrary(CPU_DLL_PATH)
    # ------------------------------------------------------

    physics_lib.calculate_acceleration.restype  = ctypes.c_float
    physics_lib.calculate_acceleration.argtypes = [
        ctypes.c_float, ctypes.POINTER(VehicleState)
    ]

    physics_lib.solve_battery_thermal_dynamics.restype  = None
    physics_lib.solve_battery_thermal_dynamics.argtypes = [
        ctypes.c_float, ctypes.c_float, ctypes.POINTER(VehicleState)
    ]

    physics_lib.run_monte_carlo_safety_check.restype  = ctypes.c_float
    physics_lib.run_monte_carlo_safety_check.argtypes = [
        ctypes.c_float, ctypes.c_float, ctypes.c_int
    ]

    CPP_AVAILABLE = True
    print("🚀 [SYSTEM] C++ Physics & Monte Carlo Engine Loaded (Zero-Copy Pointers Enabled)!")
except Exception as exc:
    print(f"⚠️  [SYSTEM] C++ Engine missing or failed ({exc}). Using Python Fallback.")

# --- FIREWALL C++ LOADER ---
FW_AVAILABLE = False
firewall_lib = None

try:
    fw_path = os.path.join(base_dir, "cpp_firewall", "firewall.dll")
    firewall_lib = ctypes.CDLL(fw_path)
    
    # Δηλώνουμε τους τύπους για την API συνάρτηση
    firewall_lib.validate_api_command.restype = ctypes.c_int
    firewall_lib.validate_api_command.argtypes = [ctypes.c_char_p]
    
    FW_AVAILABLE = True
    print("🛡️ [SECURITY] C++ Firewall DLL Loaded Successfully!")
except Exception as exc:
    print(f"⚠️ [SECURITY] Firewall DLL missing or failed ({exc}).")

# =============================================================================
# PRE-LOAD AI MODELS
# =============================================================================

print("[MEMORY] Pre-loading AI Models into RAM/VRAM...")
GLOBAL_OLLAMA_CLIENT = ollama.Client(host=OLLAMA_HOST)
GLOBAL_PPO_MODEL     = None

try:
    if os.path.exists(MODEL_PATH) or os.path.exists(MODEL_PATH + ".zip"):
        device           = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🚀 [SYSTEM] PyTorch Backend selected: {device.upper()}")
        GLOBAL_PPO_MODEL = PPO.load(MODEL_PATH, device=device)
        print("[MEMORY] PPO Model Loaded Successfully (Hardware Accelerated).")
except Exception as exc:
    print(f"⚠️  [MEMORY] PPO Load Failed: {exc}")


# =============================================================================
# DIGITAL TWIN ENVIRONMENT
# =============================================================================

class DigitalTwinEnv(gym.Env):

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__()
        self.df               = df
        self.current_step     = 0
        self.mass             = DEFAULT_MASS_KG
        self.max_power        = DEFAULT_MAX_POWER_KW
        self.gravity          = GRAVITY_MS2
        self.air_drag_coeff   = DEFAULT_AIR_DRAG_COEFF
        self.dt               = DEFAULT_DT_S
        self.current_speed_ms = 0.0
        self.soc              = DEFAULT_SOC_PCT
        self.temperature      = DEFAULT_TEMP_C

        self.action_space      = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBS_SHAPE,), dtype=np.float32
        )

    # ------------------------------------------------------------------
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> Tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self.current_step     = 0
        self.current_speed_ms = 0.0
        self.soc              = DEFAULT_SOC_PCT
        self.temperature      = DEFAULT_TEMP_C
        return self._get_obs(), {}

    # ------------------------------------------------------------------
    def _get_obs(self) -> np.ndarray:
        speed_kmh   = self.current_speed_ms * KMH_PER_MS
        noisy_speed = max(0.0, speed_kmh + np.random.normal(0, SPEED_NOISE_STD))
        dist        = self._current_column_value("Distance", DEFAULT_DISTANCE_M)
        return np.array([noisy_speed, 0.0, dist, self.soc], dtype=np.float32)

    def _current_column_value(self, col: str, fallback: float) -> float:
        """Return the value of `col` at the current step, or `fallback`."""
        if self.current_step < len(self.df) and col in self.df.columns:
            return self.df.iloc[self.current_step][col]
        return fallback

    # ------------------------------------------------------------------
    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, dict]:
        time.sleep(STEP_SLEEP_S)

        # ✅ FIX 2: Ασφαλής μετατροπή τύπου — προστασία από malformed action arrays
        # Χωρίς try/except: float(action[0]) σε corrupted numpy array → ValueError crash
        try:
            throttle = float(action[0])
        except (ValueError, TypeError) as exc:
            print(f"[WARNING] Malformed action value '{action[0]}': {exc}. Defaulting throttle to 0.0.")
            throttle = 0.0

        slope_deg = self._current_column_value("Slope", 0.0)

        if CPP_AVAILABLE:
            throttle, acceleration, energy_used_kwh = self._step_cpp(throttle, slope_deg)
        else:
            acceleration, energy_used_kwh = self._step_python(throttle, slope_deg)

        self._update_speed(acceleration)
        self.current_step += 1
        terminated = self.current_step >= len(self.df) - 1

        info = {
            "real_speed_kmh": self.current_speed_ms * KMH_PER_MS,
            "fuel":           energy_used_kwh,
            "soc":            self.soc,
            "temp_celsius":   self.temperature,
        }
        return self._get_obs(), 0.0, terminated, False, info

    # ------------------------------------------------------------------
    #  PHYSICS HELPERS
    # ------------------------------------------------------------------

    def _apply_mc_safety(self, throttle: float) -> float:
        """Run Monte Carlo risk check and zero throttle if risk is too high."""
        mc_risk = physics_lib.run_monte_carlo_safety_check(
            ctypes.c_float(self.current_speed_ms),
            ctypes.c_float(throttle),
            ctypes.c_int(MONTE_CARLO_SAMPLES),
        )
        return 0.0 if mc_risk > MC_RISK_THRESHOLD else throttle

    def _build_vehicle_state(self, slope_deg: float) -> VehicleState:
        """Snapshot current env state into the C++ VehicleState struct."""
        return VehicleState(
            speed_ms=self.current_speed_ms,
            mass=self.mass,
            air_drag_coeff=self.air_drag_coeff,
            slope_deg=slope_deg,
            soc=self.soc,
            temperature=self.temperature,
        )

    def _run_battery_dynamics(self, v_state: VehicleState, throttle: float) -> float:
        """Call C++ battery solver, write results back, return energy used (kWh)."""
        power_kw     = throttle * self.max_power
        current_amps = (power_kw * WATTS_PER_KW) / VOLTAGE_V
        physics_lib.solve_battery_thermal_dynamics(
            ctypes.c_float(current_amps), ctypes.c_float(self.dt), ctypes.byref(v_state)
        )
        self.soc         = np.clip(float(v_state.soc), SOC_MIN, SOC_MAX)
        self.temperature = float(v_state.temperature)
        return power_kw * (self.dt / SECONDS_PER_HOUR)

    def _step_cpp(
        self, throttle: float, slope_deg: float
    ) -> Tuple[float, float, float]:
        """C++ fast-path orchestrator: safety → acceleration → battery."""
        throttle     = self._apply_mc_safety(throttle)
        v_state      = self._build_vehicle_state(slope_deg)
        acceleration = physics_lib.calculate_acceleration(
            ctypes.c_float(throttle), ctypes.byref(v_state)
        )
        energy_kwh   = self._run_battery_dynamics(v_state, throttle)
        return throttle, acceleration, energy_kwh

    def _step_python(
        self, throttle: float, slope_deg: float
    ) -> Tuple[float, float]:
        """Pure-Python fallback physics."""
        power_kw         = throttle * self.max_power
        force_propulsion = (power_kw * WATTS_PER_KW) / (self.current_speed_ms + 1.0)
        force_gravity    = self.mass * self.gravity * np.sin(np.radians(slope_deg))
        force_drag       = DEFAULT_AIR_DRAG_COEFF * (self.current_speed_ms ** DRAG_FORCE_EXPONENT)
        net_force        = force_propulsion - (force_gravity + force_drag)
        acceleration     = net_force / self.mass

        energy_kwh = power_kw * (self.dt / SECONDS_PER_HOUR)
        self.soc   = np.clip(self.soc - energy_kwh * SOC_DRAIN_FACTOR, SOC_MIN, SOC_MAX)
        return acceleration, energy_kwh

    def _update_speed(self, acceleration: float) -> None:
        self.current_speed_ms = max(0.0, self.current_speed_ms + acceleration * self.dt)


# =============================================================================
# NEURO-SYMBOLIC ENGINE  –  get_driver_intent
# =============================================================================

_SYSTEM_PROMPT = """
You are the AI Control Unit of a VEHICLE SIMULATOR.
Evaluate the user command and map it to an 'urgency_score' from 0 to 10.
0 = stop/emergency/danger, 5 = normal driving, 10 = maximum speed/aggressive.
Output JSON ONLY. Format: {"urgency_score": <int>, "reasoning": "<string>"}
"""

def _parse_llm_response(content: str) -> dict:
    """Extract JSON from the LLM response string."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        return json.loads(match.group(0)) if match else {}


def _apply_symbolic_guardrails(
    score: int, reasoning: str, command: str
) -> Tuple[int, str]:
    """Override LLM score with hard safety/eco rules."""
    cmd = command.lower()
    if any(word in cmd for word in DANGER_WORDS):
        return URGENCY_DANGER_SCORE, "Symbolic Safety Layer Override: Illegal/Dangerous Command detected."
    if any(word in cmd for word in ECO_WORDS):
        return URGENCY_ECO_SCORE, "Symbolic Guardrail: Eco Mode explicitly requested."
    return score, reasoning


def _score_to_drive_params(score: int) -> Tuple[str, float]:
    """Map urgency score → (mode, aggressiveness)."""
    if score >= URGENCY_SPORT_MIN:
        return "SPORT", AGG_SPORT
    if score <= URGENCY_EMERGENCY_MAX:
        return "EMERGENCY_COAST", AGG_EMERGENCY
    if score <= URGENCY_ECO_MAX:
        return "ECO", AGG_ECO
    return "NORMAL", score / URGENCY_SCALE


def _print_engine_header() -> None:
    # ✅ FIX 3: Τα print() εδώ είναι ΣΩΣΤΑ Python 3 — το analyzer είχε false positive
    # γιατί το "print" ήταν λάθος στη _PY2_BUILTINS λίστα. Κώδικας αμετάβλητος.
    print("\n" + "=" * SEPARATOR_WIDTH)
    print("🧠 NEURO-SYMBOLIC ENGINE: SEMANTIC ANALYSIS STARTED")
    print("=" * SEPARATOR_WIDTH)


def _query_llm(user_command: str) -> dict:
    """Call the LLM and return the parsed result dict."""
    response = GLOBAL_OLLAMA_CLIENT.chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_command},
        ],
        format="json",
        options={"temperature": LLM_TEMPERATURE, "num_predict": LLM_MAX_TOKENS},
    )
    return _parse_llm_response(response["message"]["content"])


def _fallback_params(reason: str) -> Dict[str, Any]:
    return {"mode": "NORMAL", "aggressiveness": DEFAULT_AGGRESSIVENESS, "reasoning": reason}


def get_driver_intent(forced_prompt: Optional[str] = None) -> Dict[str, Any]:
    _print_engine_header()
    user_command = forced_prompt or "Drive normally"

    # 🛡️ --- ΒΗΜΑ 0: C++ FIREWALL INTERCEPTION ---
    if FW_AVAILABLE:
        # Στέλνουμε το κείμενο στη C++
        is_safe = firewall_lib.validate_api_command(user_command.encode('utf-8'))
        if not is_safe:
            # Αν η C++ βγάλει 0, μπλοκάρουμε!
            print(f"🛑 [FIREWALL] Blocked malicious intent: {user_command}")
            return _fallback_params("Action blocked by C++ Layer-7 Firewall.")

    # ✅ FIX 1 εφαρμογή: Χρήση named constant αντί magic number 0.5
    # Δίνουμε χρόνο στο τοπικό Ollama να αδειάσει τη VRAM από το προηγούμενο request
    time.sleep(LLM_CONTEXT_RESET_DELAY_S)

    try:
        result        = _query_llm(user_command)
        score         = int(result.get("urgency_score", DEFAULT_URGENCY))
        reason        = str(result.get("reasoning", "Parsed default"))
        score, reason = _apply_symbolic_guardrails(score, reason, user_command)
        mode, aggressiveness = _score_to_drive_params(score)
        return {"mode": mode, "aggressiveness": aggressiveness, "reasoning": reason}

    except Exception as exc:
        print(f"[SYSTEM ERROR] LLM Logic Failed: {exc}")
        return _fallback_params(f"Fallback due to Error: {exc}")


# =============================================================================
# ENTRY POINT
# =============================================================================

def run_live_system(
    prompt: Optional[str] = None, model_path: str = MODEL_PATH
) -> None:
    pass


if __name__ == "__main__":
    run_live_system()