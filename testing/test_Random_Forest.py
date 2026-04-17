#I observe that one column of my dataset has multiple zeros, so that can be a problem in the lstm model. I will try to remove those rows with zeros and see if the performance improves.

# data_processor.py.
#cols_to_exclude = ["Driving Cycle Type", "Target Efficiency", "Regenerative Power(kW)"] 

#Nothing has changed in lstm_model.py except the import statement comment. So no need to repeat it here.


#I observe in the plot that the lstm model remains stable at a value of 4,7. So I will run a traditional method of ML, to test if the dataset has a  problem.
#I could do it with the file named baseline_models_vasika_montela.py, but I will create a new file named test.py for clarity.
import pandas as pd
import matplotlib
matplotlib.use('Agg') #gia to docker
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score



df = pd.read_csv("data/nev_energy_management_dataset.csv")


df.replace(["N/A", "-", "unknown"], float("nan"), inplace=True)
df.dropna(inplace=True)

target = "Fuel Consumption (L/100km)"
X = df.drop([target, "Driving Cycle Type", "Target Efficiency"], axis=1, errors='ignore')
y = df[target]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)


rf_model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
rf_model.fit(X_train, y_train)

y_pred = rf_model.predict(X_test)
r2 = r2_score(y_test, y_pred)

print(f"Random Forest R2 Score: {r2:.4f}")


plt.figure(figsize=(12, 6))
plt.plot(y_test.values[:100], label='Real', color='black')
plt.plot(y_pred[:100], label='Random Forest', color='green', linestyle='--')
plt.title(f'Benchmark Test (R2: {r2:.3f})')
plt.legend()
#docker
plt.savefig("analysis_result.png") 
print("Graph saved to random_forest.png")
plt.close() #katharismos mnhmhs


# Feature Importance to observe which features are most important
importances = pd.Series(rf_model.feature_importances_, index=X.columns)
print("\nTop 5 Important Features:")
print(importances.nlargest(5))

#Results:Top 5 Importants Features: Speed (km/h)               0.155261,Acceleration (m/s²)        0.146547, Battery Power (kW)         0.141892, Engine Power (kW)          0.124949, Total Energy Used (kWh)    0.097981
# The values are normal, so there is another problem with the dataset or the lstm model. Further investigation is needed.
#We observe that there is a problem with the correlation of the target variable and the features. Possibly the dataset is not suitable for time series prediction.
#We will try a visualization solution to see if we can find some pattern.

# visualize.py
#So in this file in the first visualization we made this cocnlusion:
#When you have the correct features but no model can accurately predict the target, it means the relationship between the features and the target is not clearly defined. The dataset may contain too much noise, or a fundamental variable is missing (for example, road slope — if you’re driving uphill you consume almost twice as much fuel at the same speed, but the model has no way of knowing that).