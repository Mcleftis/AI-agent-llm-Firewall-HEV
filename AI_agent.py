import os
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
from stable_baselines3.common.callbacks import BaseCallback # <-- ΝΕΟ
from typing import Tuple, Dict
import hashlib

os.environ["OMP_NUM_THREADS"] = "1"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILENAME = os.path.join(SCRIPT_DIR, "data", "my_working_dataset.csv")
MODEL_SAVE_DIR = os.path.join(SCRIPT_DIR, "models")
MODEL_NAME = "ppo_hev"

# --- 1. ΝΕΟ: Callback για να τραβάμε τα Metrics κατά την εκπαίδευση (PPO) ---
class MetricsCallback(BaseCallback):
    def __init__(self, num_envs, verbose=0):
        super(MetricsCallback, self).__init__(verbose)
        self.num_envs = num_envs
        self.current_rewards = np.zeros(num_envs)
        self.current_violations = np.zeros(num_envs)
        
        # Εδώ αποθηκεύονται τα τελικά metrics ανά επεισόδιο
        self.episode_rewards = []
        self.episode_violations = []

    def _on_step(self) -> bool:
        rewards = self.locals["rewards"]
        dones = self.locals["dones"]
        infos = self.locals["infos"]

        for i in range(self.num_envs):
            self.current_rewards[i] += rewards[i]
            
            # Αν υπήρξε παραβίαση ορίου στο βήμα, την καταγράφουμε
            if infos[i].get("constraint_violation", False):
                self.current_violations[i] += 1

            if dones[i]:
                self.episode_rewards.append(self.current_rewards[i])
                self.episode_violations.append(self.current_violations[i])
                # Μηδενισμός για το επόμενο επεισόδιο
                self.current_rewards[i] = 0
                self.current_violations[i] = 0
        return True


class ProfessionalHybridEnv(gym.Env):
    def __init__(self, speed_arr, accel_arr, eng_pwr_arr, reg_pwr_arr, temperature: float = 25.0):
        super(ProfessionalHybridEnv, self).__init__()
        self.speed_array = speed_arr
        self.accel_array = accel_arr
        self.eng_pwr_array = eng_pwr_arr
        self.reg_pwr_array = reg_pwr_arr
        self.max_steps = len(self.speed_array) - 1
        self.temperature = temperature
        self.current_step = 0
        self.soc = 60.0
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32)
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)

    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)
        self.current_step = 0
        self.soc = 60.0
        return self._get_obs(), {}

    def _get_obs(self) -> np.ndarray:
        step = min(self.current_step, self.max_steps)
        eng_pwr = self.eng_pwr_array[step]
        reg_pwr = self.reg_pwr_array[step]
        power_demand = eng_pwr - reg_pwr
        obs = np.array([self.speed_array[step], self.accel_array[step], power_demand, self.soc], dtype=np.float32)
        return obs

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        u_engine = float(np.clip(action[0], 0.0, 1.0))
        if self.current_step >= self.max_steps:
            return self._get_obs(), 0.0, True, False, {}

        step = self.current_step
        temp_factor = 1.2 if self.temperature < 10 else (1.1 if self.temperature > 30 else 1.0)

        eng_pwr = self.eng_pwr_array[step]
        reg_pwr = self.reg_pwr_array[step]
        power_demand = eng_pwr - reg_pwr
        fuel_consumption = 0.0
        
        if power_demand <= 0:
            battery_power = power_demand
            self.soc -= (battery_power * 0.001 * (1.0 / temp_factor))
        else:
            engine_power = power_demand * u_engine
            battery_power = power_demand * (1.0 - u_engine)
            if engine_power > 0: fuel_consumption = (engine_power * 0.00025) 
            self.soc -= (battery_power * 0.001 * temp_factor)
            
        self.soc = np.clip(self.soc, 0.0, 100.0)
        reward = -(fuel_consumption * 10.0)
        
        # --- 2. ΝΕΟ: Έλεγχος Παραβιάσεων (Constraint Violations) ---
        violation = False
        if self.soc < 30: 
            reward -= 1.0 * (30 - self.soc)
            violation = True # Έπεσε κάτω από το όριο ασφαλείας
        elif self.soc > 90: 
            reward -= 1.0 * (self.soc - 90)
            violation = True # Υπερφόρτιση
            
        self.current_step += 1
        terminated = self.current_step >= self.max_steps
        
        # Στέλνουμε τη μεταβλητή violation στο info dict για να τη διαβάσει το Callback
        info = {"fuel": fuel_consumption, "soc": self.soc, "constraint_violation": violation}
        return self._get_obs(), reward, terminated, False, info


def make_env(speed_arr, accel_arr, eng_pwr_arr, reg_pwr_arr, rank, seed=0):
    def _init():
        env = ProfessionalHybridEnv(speed_arr, accel_arr, eng_pwr_arr, reg_pwr_arr)
        env.reset(seed=seed + rank)
        return env
    return _init

def generate_model_hash(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def train_ppo(steps=200000, lr=0.0003):
    print(f"\n[INFO] Starting High-Performance Multi-Process Training")
    if not os.path.exists(DATA_FILENAME):
        print(f"[ERROR] Dataset not found: {DATA_FILENAME}")
        return

    df = pd.read_csv(DATA_FILENAME)
    df.columns = df.columns.str.strip() 
    speed_arr = df['Speed (km/h)'].to_numpy(dtype=np.float32)
    accel_arr = df['Acceleration (m/s²)'].to_numpy(dtype=np.float32)
    eng_pwr_arr = df['Engine Power (kW)'].to_numpy(dtype=np.float32)
    reg_pwr_arr = df['Regenerative Braking Power (kW)'].to_numpy(dtype=np.float32) if 'Regenerative Braking Power (kW)' in df.columns else np.zeros(len(df), dtype=np.float32)
    del df

    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    save_path = os.path.join(MODEL_SAVE_DIR, MODEL_NAME)

    NUM_PROCESSES = 8 
    env_fns = [make_env(speed_arr, accel_arr, eng_pwr_arr, reg_pwr_arr, i) for i in range(NUM_PROCESSES)]
    env = SubprocVecEnv(env_fns)
    env = VecNormalize(env, norm_obs=True, norm_reward=True, clip_obs=10.)

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Αρχικοποίηση του Callback
    metrics_callback = MetricsCallback(num_envs=NUM_PROCESSES)
    
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=lr, device=device)
    print("[INFO] Training started... 🔥")
    
    # Περνάμε το callback στην learn()
    model.learn(total_timesteps=steps, callback=metrics_callback)
    
    # Εκτύπωση αποτελεσμάτων στο τέλος (Μπορείς να τα κάνεις plot από εδώ)
    print(f"\n--- TRAINING METRICS ---")
    print(f"Total Episodes completed: {len(metrics_callback.episode_rewards)}")
    print(f"Average Reward (Last 100): {np.mean(metrics_callback.episode_rewards[-100:]):.2f}")
    print(f"Total Constraint Violations: {np.sum(metrics_callback.episode_violations)}")
    
    model.save(save_path)
    env.save(f"{save_path}_vecnormalize.pkl")
    final_model_path = f"{save_path}.zip"
    if os.path.exists(final_model_path):
        model_hash = generate_model_hash(final_model_path)
        with open(f"{save_path}.sha256", "w") as f:
            f.write(model_hash)
    env.close()

if __name__ == "__main__":
    train_ppo()