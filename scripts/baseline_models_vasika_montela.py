import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import os
import matplotlib
matplotlib.use('Agg') #gia to docker
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
import xgboost as xgb

import tensorflow as tf
from tensorflow import keras
import cv2

import nltk
from deap import base, creator, tools

import kagglehub
from kagglehub import KaggleDatasetAdapter
import xgboost as xgb

from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.metrics import accuracy_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout

import pandas as pd
import os
import sys


current_dir = os.path.dirname(os.path.abspath(__file__))


ROOT_DIR = os.path.abspath(os.path.join(current_dir, '..'))


sys.path.append(ROOT_DIR)


DATA_PATH = os.path.join(ROOT_DIR, "data", "my_working_dataset.csv")

print(f"Loading data from: {DATA_PATH}")


if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH)
else:
    print("Error: Dataset not found!")

print(df.head())
print(df.info())


print("The columns of the dataset are:", df.columns)




df.replace(["N/A","-","unknown"], np.nan, inplace=True)




cols_to_exclude = ["Driving Cycle Type", "Target Efficiency"]


cols_to_fix = [c for c in df.columns if c not in cols_to_exclude]


for col in cols_to_fix:
    df[col]=pd.to_numeric(df[col], errors='coerce')


df=df.dropna()
df=df.drop_duplicates()


numeric_cols=df.select_dtypes(include=[np.number]).columns



for col in numeric_cols:
   Q1=df[col].quantile(0.25)
   Q3=df[col].quantile(0.75)
   IQR=Q3-Q1
   df=df[(df[col] >= Q1-1.5*IQR) & (df[col] <= Q3+1.5*IQR)]




if "Driving Cycle Type" in df.columns:
    print("Encoding 'Driving Cycle Type'...")
    df = pd.get_dummies(df, columns=["Driving Cycle Type"], drop_first=True)
else:
    print("Column 'Driving Cycle Type' missing. Skipping encoding (Not needed for this dataset).")
print("Megethos Dataset(Dataset Size)", df.shape)


if 'Target Efficiency' in df.columns:
    df = df.drop('Target Efficiency', axis=1)




target_col="Fuel Consumption (L/100km)"

X=df.drop(target_col, axis=1)
y=df[target_col]

X_train, X_test, y_train, y_test=train_test_split(
    X,y,
    test_size=0.2,
    random_state=42
)



scaler=MinMaxScaler()
X_train_scaled=scaler.fit_transform(X_train)
X_test_scaled=scaler.transform(X_test)



model=LinearRegression()
model.fit(X_train_scaled, y_train)
y_pred=model.predict(X_test_scaled)
print("MSE:", mean_squared_error(y_test, y_pred))
print("MAE:", mean_absolute_error(y_test, y_pred))
print("R^2", r2_score(y_test,y_pred))


results_df = pd.DataFrame({'Real': y_test.values, 'Predict': y_pred})
print(results_df.head())

print("We see that we have negative score of R^2, so we can understand that we cannot solve our problem with Linear Regression.")


model2=xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, random_state=42)
model2.fit(X_train_scaled, y_train)
y_pred_xgb=model2.predict(X_test_scaled)
mae=mean_absolute_error(y_test, y_pred_xgb)
print("MAE meta apo xgboost:", mae)
r2_xgb=r2_score(y_test, y_pred_xgb)
print("R2 score xgboost:", r2_xgb)


model=Sequential([
    Dense(64, activation='relu', input_shape=(X_train_scaled.shape[1],)),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dense(1)
])

model.compile(optimizer='adam', loss='mse', metrics=['mae'])

print("Ekpaidefsh nevrwnikou diktyou(Neural Network Training)")
history=model.fit(
    X_train_scaled, y_train,
    validation_split=0.2,
    epochs=50,
    batch_size=32,
    verbose=1
)

y_pred_nn=model.predict(X_test_scaled)
r2_nn=r2_score(y_test, y_pred_nn)
mae_nn=mean_absolute_error(y_test, y_pred_nn)

print(f"R² Score Neural Network: {r2_nn:.5f}")
print(f"MAE Neural Network: {mae_nn:.4f} L/100km")



plt.figure(figsize=(15,6))
plt.plot(y_test.values, color='blue', linewidth=2, label="Real Consumption")
plt.plot(y_pred_xgb, color='green', linestyle='--', label="XGBoost")
plt.plot(y_pred_nn, color='red', linestyle=':', label="Neural Network")

plt.title('Compare real vs Predicted Values (XGBoost)', fontsize=16)
plt.xlabel('Δείγματα Διαδρομής/Route Samples,  (Χρόνος/Time)', fontsize=12)
plt.ylabel('Κατανάλωση/Consumption (L/100km)', fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)

plt.savefig("analysis_result.png") 
print("Graph saved to baseline_models.png")
plt.close() #katharismos mnhmhs
