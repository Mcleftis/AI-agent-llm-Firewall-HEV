import pandas as pd
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from stable_baselines3 import PPO



DATA_FILENAME = "data/my_working_dataset.csv"
MODEL_PATH = "final_hybrid_agent_model"


class ProfessionalHybridEnv(gym.Env):
    def __init__(self, df):
        super(ProfessionalHybridEnv, self).__init__()
        self.df = df
        self.current_step = 0
        self.soc = 60.0 
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(4,), dtype=np.float32)
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        self.soc = 60.0 
        return self._get_obs(), {}

    def _get_obs(self):
        row = self.df.iloc[self.current_step]
        eng_pwr = row.get('Engine Power (kW)', 0)
        reg_pwr = row.get('Regenerative Braking Power (kW)', 0)
        power_demand = eng_pwr - reg_pwr
        return np.array([row.get('Speed (km/h)', 0), row.get('Acceleration (m/s²)', 0), power_demand, self.soc], dtype=np.float32)

    def step(self, action):
        u_engine = float(action[0])
        row = self.df.iloc[self.current_step]
        eng_pwr = row.get('Engine Power (kW)', 0)
        reg_pwr = row.get('Regenerative Braking Power (kW)', 0)
        power_demand = eng_pwr - reg_pwr
        
        fuel_consumption = 0.0
        battery_power = 0.0
        
        if power_demand <= 0:
            battery_power = power_demand
            self.soc -= (battery_power * 0.7) / 100 
        else:
            engine_power = power_demand * u_engine
            battery_power = power_demand * (1.0 - u_engine)
            if engine_power > 0: fuel_consumption = (engine_power * 0.00025) 
            self.soc -= (battery_power * 0.05) 
            
        self.soc = np.clip(self.soc, 0, 100)
        self.current_step += 1
        terminated = self.current_step >= len(self.df) - 1
        
        return self._get_obs(), 0, terminated, False, {"fuel": fuel_consumption}


if __name__ == "__main__":
    df = pd.read_csv(DATA_FILENAME)
    df.columns = df.columns.str.strip() 
    

    env_ai = ProfessionalHybridEnv(df)
    env_dumb = ProfessionalHybridEnv(df) #Xazos odhgos mono venzinh
    
    
    print("Loading AI Agent...")
    try:
        model = PPO.load(MODEL_PATH)
    except:
        print("No model found. Run the training first")
        exit()

    print("\nAI vs DUMB ENGINE")
    
    steps_to_test = 1000
    

    obs, _ = env_ai.reset()
    fuel_ai = 0
    for _ in range(steps_to_test):
        action, _ = model.predict(obs)
        obs, _, done, _, info = env_ai.step(action)
        fuel_ai += info['fuel']
        if done: break
        

    obs, _ = env_dumb.reset()
    fuel_dumb = 0
    for _ in range(steps_to_test):
        action = [1.0] 
        obs, _, done, _, info = env_dumb.step(action)
        fuel_dumb += info['fuel']
        if done: break

    print("\n" + "="*40)
    print("         Results        ")
    print("="*40)
    print(f"Conventional Car (Dumb):  {fuel_dumb:.2f} Liters")
    print(f"AI Agent:            {fuel_ai:.2f} Liters")
    print("-" * 40)
    
    savings = fuel_dumb - fuel_ai
    percentage = (savings / fuel_dumb) * 100 if fuel_dumb > 0 else 0
    
    if savings > 0:
        print(f"Gain: {savings:.2f} Λίτρα")
        print(f"Improvement: {percentage:.1f}% !!")
    else:
        print(f"AI lost by{-savings:.2f} Liters.")
        print("Run training again for better results(for example 200.000).")
    print("="*40)