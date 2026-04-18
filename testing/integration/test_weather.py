import pandas as pd
import matplotlib
matplotlib.use('Agg') #gia to docker
import matplotlib.pyplot as plt
from stable_baselines3 import PPO
from AI_agent import ProfessionalHybridEnv, DATA_FILENAME

df = pd.read_csv(DATA_FILENAME)
df.columns = df.columns.str.strip()
if 'Regenerative Braking Power (kW)' not in df.columns: df['Regenerative Braking Power (kW)'] = 0.0

model = PPO.load("models/ppo_hev") 

results = {}

#3 senaria
scenarios = {
    "Winter (-5°C)": -5,
    "Spring (25°C)": 25,
    "Heatwave (40°C)": 40
}

for season, temp in scenarios.items():
    print(f"Testing Scenario: {season}...")
    
  
    env = ProfessionalHybridEnv(df, temperature=temp)
    
    obs, _ = env.reset()
    total_fuel = 0
    done = False
    
    while not done:
        action, _ = model.predict(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total_fuel += info['fuel']
        done = terminated or truncated
        
    results[season] = total_fuel
    print(f"   Fuel Consumed: {total_fuel:.2f} Liters")

# Visualisation
plt.figure(figsize=(8, 5))
plt.bar(results.keys(), results.values(), color=['#3498db', '#2ecc71', '#e74c3c'])
plt.title("Impact of Weather on HEV Fuel Consumption")
plt.ylabel("Fuel (Liters)")
plt.savefig("weather_impact.png")
print("Graph saved: weather_impact.png")