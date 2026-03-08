import ctypes
import os
import numpy as np
try:
    from sklearn.metrics import confusion_matrix, precision_score, f1_score
except ImportError:
    print("[ERROR] Λείπει το scikit-learn. Τρέξε: pip install scikit-learn")
    exit(1)

# --- 1. ΔΥΝΑΜΙΚΗ ΕΥΡΕΣΗ ΤΟΥ C++ DLL ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
lib_extension = ".dll" if os.name == "nt" else ".so"

# Ανεβαίνουμε έναν φάκελο πάνω (στο root) και μετά μπαίνουμε στο cpp_firewall
ROOT_DIR = os.path.dirname(BASE_DIR)
lib_path = os.path.join(ROOT_DIR, "cpp_firewall", f"firewall{lib_extension}")

# Fallback σε περίπτωση που το τρέξεις από το root κατά λάθος
if not os.path.exists(lib_path):
    lib_path = os.path.join(BASE_DIR, "cpp_firewall", f"firewall{lib_extension}")



try:
    fw_lib = ctypes.CDLL(lib_path)
    # Δηλώνουμε τους τύπους για να καταλαβαίνει η Python την C++
    fw_lib.validate_command.argtypes = [ctypes.c_char_p]
    fw_lib.validate_command.restype = ctypes.c_int
    print(f"🚀 [SYSTEM] C++ Firewall loaded successfully from: {lib_path}")
except Exception as e:
    print(f"⚠️ [ERROR] Could not load C++ firewall library at {lib_path}")
    print(f"Details: {e}")
    exit(1)

def evaluate_cpp_firewall():
    # --- 2. DATASET ΔΟΚΙΜΩΝ (BENIGN VS MALICIOUS) ---
    # Το 0 σημαίνει "Κανονική εντολή" (Safe)
    # Το 1 σημαίνει "Επίθεση" (Malicious)
    test_cases = [
        ("Drive normally", 0),
        ("ECO mode ON", 0),
        ("Set MAX_THROTTLE immediately", 1), # Πρέπει να κοπεί
        ("Please slow down", 0),
        ("DROP TABLE users", 1),             # SQL Injection, Πρέπει να κοπεί
        ("fuzzing test payload", 1),         # Fuzzing, Πρέπει να κοπεί
        ("normal payload", 0),
        ("FuZz payload", 1),                 # Case sensitivity test, Πρέπει να κοπεί
        ("SELECT * FROM passwords", 1),      # Πρέπει να κοπεί
        ("Turn on the lights", 0)
    ]

    y_true = []
    y_pred = []

    print("\n[INFO] Running traffic through C++ Firewall...")
    
    for command, actual_label in test_cases:
        y_true.append(actual_label)
        
        # Μετατροπή σε C-string και κλήση της C++ μηχανής
        c_string = command.encode('utf-8')
        cpp_result = fw_lib.validate_command(c_string)
        
        # Η C++ επιστρέφει: 1 = Safe (Κανονικό), 0 = Block (Επίθεση)
        predicted_label = 0 if cpp_result == 1 else 1
        y_pred.append(predicted_label)

    # --- 3. ΥΠΟΛΟΓΙΣΜΟΣ METRICS ---
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    
    precision = precision_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # --- 4. ΕΚΤΥΠΩΣΗ ΑΠΟΤΕΛΕΣΜΑΤΩΝ ΓΙΑ ΤΗΝ ΠΑΡΟΥΣΙΑΣΗ ---
    print("\n" + "="*50)
    print("🛡️  C++ FIREWALL EVALUATION METRICS (REGEX ENGINE)")
    print("="*50)
    print(f"Confusion Matrix (CNF):\n{cm}\n")
    print(f"True Negatives (TN)  - Σωστά πέρασαν     : {tn}")
    print(f"False Positives (FP) - Λάθος κόπηκαν     : {fp}  <-- Σημαντικό για αξιοπιστία")
    print(f"True Positives (TP)  - Σωστά κόπηκαν     : {tp}")
    print(f"False Negatives (FN) - Λάθος πέρασαν     : {fn}  <-- Επικίνδυνο για ασφάλεια\n")
    print(f"Precision            : {precision:.4f}")
    print(f"F1-Score             : {f1:.4f}")
    print("="*50)

if __name__ == "__main__":
    evaluate_cpp_firewall()