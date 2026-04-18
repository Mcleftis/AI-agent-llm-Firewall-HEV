import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

# ==========================================
# ΚΑΘΟΛΙΚΕΣ ΣΤΑΘΕΡΕΣ (CONSTANTS)
# ==========================================
DATA_PATH = "data/nev_energy_management_dataset.csv"
TARGET_COL = "Battery Power (kW)"

VEHICLE_MASS_KG = 1500
AIR_DENSITY = 1.225         # kg/m^3
DRAG_COEFFICIENT = 0.3      # Cd
FRONTAL_AREA = 2.2          # m^2
ROLLING_RESISTANCE = 0.015  # Crr
GRAVITY = 9.81              # m/s^2

# ==========================================
# ΣΥΝΑΡΤΗΣΕΙΣ (MODULAR DESIGN)
# ==========================================

def load_and_clean_data(filepath: str) -> tuple[pd.DataFrame, str]:
    """Φορτώνει το CSV, καθαρίζει τα κενά και αφαιρεί τα outliers."""
    print("Loading and cleaning data...")
    df = pd.read_csv(filepath)
    
    df.replace(["N/A", "-", "unknown"], float("nan"), inplace=True)
    df.dropna(inplace=True)

    speed_col = [c for c in df.columns if 'Speed' in c][0]
    
    # Φιλτράρισμα: Όχι αρνητικές ταχύτητες, όχι αρνητική ή μηδενική μπαταρία (για αυτό το τεστ)
    df = df[(df[speed_col] >= 0) & (df[TARGET_COL] > 0)]
    
    return df, speed_col


def engineer_physics_features(df: pd.DataFrame, speed_col: str) -> pd.DataFrame:
    """Υπολογίζει τις δυνάμεις της Φυσικής (Αεροδυναμική, Τριβή, Επιτάχυνση)."""
    print("Performing Advanced Physics Feature Engineering...")
    df = df.copy() # Αποφυγή SettingWithCopyWarning
    
    # Μετατροπές
    df['Speed_m_s'] = df[speed_col] / 3.6
    df['Acceleration_m_s2'] = df['Speed_m_s'].diff().fillna(0)
    df['Accel_Positive'] = df['Acceleration_m_s2'].apply(lambda x: x if x > 0 else 0)

    # Φυσικές Δυνάμεις
    df['Aero_Drag_Force'] = 0.5 * AIR_DENSITY * DRAG_COEFFICIENT * FRONTAL_AREA * (df['Speed_m_s']**2)
    df['Rolling_Friction_Force'] = ROLLING_RESISTANCE * VEHICLE_MASS_KG * GRAVITY
    df['Acceleration_Force'] = VEHICLE_MASS_KG * df['Accel_Positive']

    # Συνολική Απαιτούμενη Ισχύς
    df['Total_Required_Power_Watts'] = (df['Aero_Drag_Force'] + df['Rolling_Friction_Force'] + df['Acceleration_Force']) * df['Speed_m_s']
    
    return df


def train_and_evaluate(df: pd.DataFrame):
    """Εκπαιδεύει τον Random Forest αποφεύγοντας το Data Leakage."""
    print("Training Random Forest without Data Leakage...")
    
    # Πετάμε έξω ΟΤΙΔΗΠΟΤΕ προδίδει άμεσα τη μπαταρία (Αποφυγή Κλεψίματος)
    leaky_columns = [
        TARGET_COL, 
        "Fuel Consumption (L/100km)", 
        "Engine Power (kW)", 
        "Power Demand (kW)", 
        "Driving Cycle Type", 
        "Target Efficiency"
    ]
    X = df.drop(columns=leaky_columns, errors='ignore')
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    rf_model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
    rf_model.fit(X_train, y_train)

    y_pred = rf_model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    
    return rf_model, X.columns, r2


def plot_results(df: pd.DataFrame, r2: float):
    """Οπτικοποιεί τα αποτελέσματα (Διορθωμένα labels)."""
    plt.figure(figsize=(10, 6))
    sample_df = df.sample(n=min(1000, len(df)), random_state=42)
    
    sns.scatterplot(x=sample_df['Total_Required_Power_Watts'], y=sample_df[TARGET_COL], alpha=0.5)
    
    plt.title(f"Physics Power vs {TARGET_COL} (R2={r2:.3f})\nVerification of True Predictive Power")
    plt.xlabel("Total Calculated Physics Power (Watts)")
    plt.ylabel(TARGET_COL)
    
    plt.tight_layout()
    plt.savefig("physics_vs_battery.png")
    print("Saved visualization to physics_vs_battery.png.")


# ==========================================
# MAIN EXECUTION (ENTRY POINT)
# ==========================================
if __name__ == "__main__":
    # 1. Load Data
    df, speed_col = load_and_clean_data(DATA_PATH)
    
    # 2. Feature Engineering
    df = engineer_physics_features(df, speed_col)
    
    # 3. Model Training
    model, feature_names, r2 = train_and_evaluate(df)
    
    # 4. Results
    print("\n=========================================")
    print(f"FINAL Random Forest R2 Score: {r2:.4f}")
    print("=========================================")
    
    # 5. Visualization
    plot_results(df, r2)
    
    # 6. Feature Importance
    importances = pd.Series(model.feature_importances_, index=feature_names)
    print("\nTop 5 Important Features:")
    print(importances.nlargest(5))