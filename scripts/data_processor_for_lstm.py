
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler


def get_data_ready(filepath):
    df = pd.read_csv(filepath)

    
    features = ['Speed (km/h)', 'Acceleration (m/s²)', 'Engine Power (kW)', 'Regenerative Braking Power (kW)']
    target = 'Fuel Consumption (L/100km)'

    X = df[features].values
    y = df[target].values

    scaler_X = MinMaxScaler()
    X_scaled = scaler_X.fit_transform(X)

    scaler_y = MinMaxScaler()
    y_scaled = scaler_y.fit_transform(y.reshape(-1, 1))

    return X_scaled, y_scaled, scaler_y

def create_sequences(X, y, time_steps=60):
    Xs, ys = [], []
    for i in range(len(X) - time_steps):
        Xs.append(X[i:(i + time_steps)])
        ys.append(y[i + time_steps])
    return np.array(Xs), np.array(ys)