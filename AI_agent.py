import os
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
from stable_baselines3.common.callbacks import BaseCallback
from typing import Tuple, Dict, List
from dataclasses import dataclass
import hashlib

HASH_CHUNK_SIZE=4096

os.environ["OMP_NUM_THREADS"] = "1"

# =============================================================================
# PATH CONSTANTS
# =============================================================================

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_FILENAME  = os.path.join(SCRIPT_DIR, "data", "my_working_dataset.csv")
MODEL_SAVE_DIR = os.path.join(SCRIPT_DIR, "models")
MODEL_NAME     = "ppo_hev"

# =============================================================================
# ENVIRONMENT CONSTANTS  (no magic numbers anywhere below this block)
# =============================================================================

# --- Initial state ---
INITIAL_SOC_PCT          = 60.0    # Starting State-of-Charge (%)
DEFAULT_TEMPERATURE_C    = 25.0    # Default ambient temperature (°C)

# --- Temperature thresholds & penalty factors ---
TEMP_COLD_THRESHOLD_C    = 10.0    # Below this → cold penalty applies
TEMP_HOT_THRESHOLD_C     = 30.0    # Above this → heat penalty applies
TEMP_COLD_FACTOR         = 1.2     # Efficiency multiplier when cold
TEMP_HOT_FACTOR          = 1.1     # Efficiency multiplier when hot
TEMP_NOMINAL_FACTOR      = 1.0     # Nominal efficiency multiplier

# --- Battery limits ---
SOC_MIN_PCT              = 0.0
SOC_MAX_PCT              = 100.0
SOC_SAFE_LOW_PCT         = 30.0    # Below this → constraint violation
SOC_SAFE_HIGH_PCT        = 90.0    # Above this → constraint violation (overcharge)

# --- Physics / energy coefficients ---
BATTERY_POWER_COEFF      = 0.001   # kW → SoC drain factor per step
FUEL_CONSUMPTION_COEFF   = 0.00025 # kW → fuel units per step

# --- Reward shaping ---
FUEL_REWARD_SCALE        = 10.0    # Multiplier on fuel penalty in reward
SOC_VIOLATION_PENALTY    = 1.0     # Penalty coefficient per % outside safe range

# --- Training ---
DEFAULT_TRAIN_STEPS      = 200_000
DEFAULT_LEARNING_RATE    = 0.0003
NUM_PROCESSES            = 8
OBS_CLIP                 = 10.0    # VecNormalize clip_obs value

# --- Hashing ---
METRICS_LAST_N_EPISODES  = 100   # Window for average-reward reporting
OBS_SPACE_SHAPE          = 4     # [speed, accel, power_demand, soc]

# =============================================================================
# PARAMETER OBJECTS  (eliminates argument overload violations)
# =============================================================================

@dataclass
class EnvArrays:
    """
    Groups the four per-step telemetry arrays used by ProfessionalHybridEnv
    and make_env into a single Parameter Object.
    Reduces constructor arity from 6 → 2  (self + EnvArrays + temperature).
    """
    speed_arr:   np.ndarray
    accel_arr:   np.ndarray
    eng_pwr_arr: np.ndarray
    reg_pwr_arr: np.ndarray


# =============================================================================
# METRICS CALLBACK
# =============================================================================

class MetricsCallback(BaseCallback):
    """Collects per-episode reward and constraint-violation stats during training."""

    def __init__(self, num_envs: int, verbose: int = 0) -> None:
        super().__init__(verbose)
        self.num_envs            = num_envs
        self.current_rewards     = np.zeros(num_envs)
        self.current_violations  = np.zeros(num_envs)
        self.episode_rewards:    List[float] = []
        self.episode_violations: List[float] = []

    def _on_step(self) -> bool:
        rewards = self.locals["rewards"]
        dones   = self.locals["dones"]
        infos   = self.locals["infos"]

        for i in range(self.num_envs):
            self.current_rewards[i] += rewards[i]
            if infos[i].get("constraint_violation", False):
                self.current_violations[i] += 1

            if dones[i]:
                self.episode_rewards.append(float(self.current_rewards[i]))
                self.episode_violations.append(float(self.current_violations[i]))
                self.current_rewards[i]    = 0.0
                self.current_violations[i] = 0.0

        return True


# =============================================================================
# ENVIRONMENT
# =============================================================================

class ProfessionalHybridEnv(gym.Env):

    def __init__(
        self,
        arrays:      EnvArrays,
        temperature: float = DEFAULT_TEMPERATURE_C,
    ) -> None:
        super().__init__()
        self.speed_array   = arrays.speed_arr
        self.accel_array   = arrays.accel_arr
        self.eng_pwr_array = arrays.eng_pwr_arr
        self.reg_pwr_array = arrays.reg_pwr_arr
        self.max_steps     = len(self.speed_array) - 1
        self.temperature   = temperature
        self.current_step  = 0
        self.soc           = INITIAL_SOC_PCT

        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBS_SPACE_SHAPE,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=0.0, high=1.0, shape=(1,), dtype=np.float32
        )

    # ------------------------------------------------------------------
    def reset(
        self,
        seed:    int | None  = None,
        options: dict | None = None,
    ) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)
        self.current_step = 0
        self.soc          = INITIAL_SOC_PCT
        return self._get_obs(), {}

    # ------------------------------------------------------------------
    def _get_obs(self) -> np.ndarray:
        step         = min(self.current_step, self.max_steps)
        power_demand = self.eng_pwr_array[step] - self.reg_pwr_array[step]
        return np.array(
            [self.speed_array[step], self.accel_array[step], power_demand, self.soc],
            dtype=np.float32,
        )

    # ------------------------------------------------------------------
    def step(
        self, action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        u_engine = float(np.clip(action[0], SOC_MIN_PCT / SOC_MAX_PCT, 1.0))

        if self.current_step >= self.max_steps:
            return self._get_obs(), 0.0, True, False, {}

        fuel_consumption, soc_delta = self._compute_energy(u_engine)
        self.soc = float(np.clip(self.soc + soc_delta, SOC_MIN_PCT, SOC_MAX_PCT))

        reward, violation = self._calculate_reward(fuel_consumption)

        self.current_step += 1
        terminated = self.current_step >= self.max_steps

        info: Dict = {
            "fuel":                 fuel_consumption,
            "soc":                  self.soc,
            "constraint_violation": violation,
        }
        return self._get_obs(), reward, terminated, False, info

    # ------------------------------------------------------------------
    #  PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _temp_factor(self) -> float:
        """Return the temperature efficiency multiplier for the current step."""
        if self.temperature < TEMP_COLD_THRESHOLD_C:
            return TEMP_COLD_FACTOR
        if self.temperature > TEMP_HOT_THRESHOLD_C:
            return TEMP_HOT_FACTOR
        return TEMP_NOMINAL_FACTOR

    def _compute_energy(self, u_engine: float) -> Tuple[float, float]:
        """
        Pure physics calculation – no side-effects on self.soc.

        Returns
        -------
        fuel_consumption : float
            Fuel used this step (arbitrary units).
        soc_delta : float
            Change in SoC this step (negative = discharge).
        """
        step         = self.current_step
        temp_factor  = self._temp_factor()
        power_demand = self.eng_pwr_array[step] - self.reg_pwr_array[step]

        if power_demand <= 0:
            # Regenerative / coasting – battery charges
            soc_delta        = -(power_demand * BATTERY_POWER_COEFF * (1.0 / temp_factor))
            fuel_consumption = 0.0
        else:
            engine_power     = power_demand * u_engine
            battery_power    = power_demand * (1.0 - u_engine)
            fuel_consumption = (engine_power * FUEL_CONSUMPTION_COEFF) if engine_power > 0 else 0.0
            soc_delta        = -(battery_power * BATTERY_POWER_COEFF * temp_factor)

        return fuel_consumption, soc_delta

    def _calculate_reward(self, fuel_consumption: float) -> Tuple[float, bool]:
        """
        Compute the shaped reward and detect constraint violations.
        Extracted from step() to keep branching complexity low.

        Returns
        -------
        reward    : float
        violation : bool
        """
        reward    = -(fuel_consumption * FUEL_REWARD_SCALE)
        violation = False

        if self.soc < SOC_SAFE_LOW_PCT:
            reward    -= SOC_VIOLATION_PENALTY * (SOC_SAFE_LOW_PCT - self.soc)
            violation  = True
        elif self.soc > SOC_SAFE_HIGH_PCT:
            reward    -= SOC_VIOLATION_PENALTY * (self.soc - SOC_SAFE_HIGH_PCT)
            violation  = True

        return reward, violation


# =============================================================================
# FACTORY + HASH HELPERS
# =============================================================================

def make_env(
    arrays: EnvArrays,
    rank:   int,
    seed:   int = 0,
) -> callable:
    """Return a callable that builds and seeds a single environment instance."""
    def _init() -> ProfessionalHybridEnv:
        env = ProfessionalHybridEnv(arrays)
        env.reset(seed=seed + rank)
        return env
    return _init


def generate_model_hash(filepath: str) -> str:
    """Compute SHA-256 digest of a file, reading in fixed-size chunks."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as file_handle:
        for byte_block in iter(lambda: file_handle.read(HASH_CHUNK_SIZE), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


# =============================================================================
# TRAINING ENTRY POINT
# =============================================================================

def _load_telemetry() -> EnvArrays:
    """Read the CSV dataset and return arrays packed into an EnvArrays object."""
    telemetry_data         = pd.read_csv(DATA_FILENAME)
    telemetry_data.columns = telemetry_data.columns.str.strip()

    speed_arr   = telemetry_data["Speed (km/h)"].to_numpy(dtype=np.float32)
    accel_arr   = telemetry_data["Acceleration (m/s²)"].to_numpy(dtype=np.float32)
    eng_pwr_arr = telemetry_data["Engine Power (kW)"].to_numpy(dtype=np.float32)
    reg_pwr_arr = (
        telemetry_data["Regenerative Braking Power (kW)"].to_numpy(dtype=np.float32)
        if "Regenerative Braking Power (kW)" in telemetry_data.columns
        else np.zeros(len(telemetry_data), dtype=np.float32)
    )
    return EnvArrays(speed_arr, accel_arr, eng_pwr_arr, reg_pwr_arr)


def _build_vec_env(arrays: EnvArrays) -> VecNormalize:
    """Spawn SubprocVecEnv workers and wrap with VecNormalize."""
    env_fns = [make_env(arrays, rank=i) for i in range(NUM_PROCESSES)]
    vec_env = SubprocVecEnv(env_fns)
    return VecNormalize(vec_env, norm_obs=True, norm_reward=True, clip_obs=OBS_CLIP)


def _save_model_and_hash(model: PPO, vec_env: VecNormalize, save_path: str) -> None:
    """Persist the trained model, VecNormalize stats, and SHA-256 integrity file."""
    model.save(save_path)
    vec_env.save(f"{save_path}_vecnormalize.pkl")

    final_model_path = f"{save_path}.zip"
    if os.path.exists(final_model_path):
        model_hash = generate_model_hash(final_model_path)
        with open(f"{save_path}.sha256", "w") as hash_file:
            hash_file.write(model_hash)


def train_ppo(
    steps:   int   = DEFAULT_TRAIN_STEPS,
    lr:      float = DEFAULT_LEARNING_RATE,
    traffic: str   = "normal",
) -> None:
    """Orchestrate data loading, environment setup, PPO training, and model saving."""
    print("\n[INFO] Starting High-Performance Multi-Process Training")

    if not os.path.exists(DATA_FILENAME):
        print(f"[ERROR] Dataset not found: {DATA_FILENAME}")
        return

    arrays  = _load_telemetry()
    vec_env = _build_vec_env(arrays)

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    metrics_callback = MetricsCallback(num_envs=NUM_PROCESSES)
    model = PPO("MlpPolicy", vec_env, verbose=1, learning_rate=lr, device=device)

    print("[INFO] Training started... 🔥")
    model.learn(total_timesteps=steps, callback=metrics_callback)
    _print_training_summary(metrics_callback)

    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    _save_model_and_hash(model, vec_env, os.path.join(MODEL_SAVE_DIR, MODEL_NAME))
    vec_env.close()


def _print_training_summary(callback: MetricsCallback) -> None:
    """Print end-of-training metrics extracted by MetricsCallback."""
    print("\n--- TRAINING METRICS ---")
    print(f"Total Episodes completed  : {len(callback.episode_rewards)}")
    print(
        f"Average Reward (Last {METRICS_LAST_N_EPISODES}): "
        f"{np.mean(callback.episode_rewards[-METRICS_LAST_N_EPISODES:]):.2f}"
    )
    print(f"Total Constraint Violations: {int(np.sum(callback.episode_violations))}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    train_ppo()