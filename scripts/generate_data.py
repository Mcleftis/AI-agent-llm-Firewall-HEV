import pandas as pd
import numpy as np
import os


save_path = "data/my_working_dataset.csv"


n_samples = 5000
time = np.arange(n_samples)


speed = 40 + 25 * np.sin(time * 0.005) + 15 * np.sin(time * 0.015)
speed = np.maximum(speed, 0)


acceleration = np.gradient(speed)


total_power_demand = (0.5 * speed) + (20 * acceleration * speed)


engine_power = np.where(total_power_demand > 0, total_power_demand, 0)


regen_power = np.where(total_power_demand < 0, -total_power_demand * 0.7, 0)


fuel_consumption = (engine_power * 0.1) + np.random.normal(0, 0.01, n_samples)
fuel_consumption = np.maximum(fuel_consumption, 0.2) 


df = pd.DataFrame({
    'Speed (km/h)': speed,
    'Acceleration (m/s²)': acceleration,
    'Engine Power (kW)': engine_power,
    'Regenerative Braking Power (kW)': regen_power,
    'Fuel Consumption (L/100km)': fuel_consumption
})


folder = os.path.dirname(save_path)
if not os.path.exists(folder):
    os.makedirs(folder)

df.to_csv(save_path, index=False)
print(f"New dataset created at: {save_path}")
print("Now the columns are:", df.columns.tolist())