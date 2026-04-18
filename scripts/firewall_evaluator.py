import ctypes
import os
import time
try:
    from sklearn.metrics import confusion_matrix, precision_score, f1_score, recall_score
except ImportError:
    print("[ERROR] Λείπει το scikit-learn. Τρέξε: pip install scikit-learn")
    exit(1)

# --- 1. ΔΥΝΑΜΙΚΗ ΕΥΡΕΣΗ ΤΟΥ C++ DLL ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
lib_extension = ".dll" if os.name == "nt" else ".so"

ROOT_DIR = os.path.dirname(BASE_DIR)
lib_path = os.path.join(ROOT_DIR, "cpp_firewall", f"firewall{lib_extension}")

if not os.path.exists(lib_path):
    lib_path = os.path.join(BASE_DIR, "cpp_firewall", f"firewall{lib_extension}")

try:
    fw_lib = ctypes.CDLL(lib_path)
    # SOS: Πρέπει να γράψουμε validate_api_command, όχι validate_command
    fw_lib.validate_api_command.argtypes = [ctypes.c_char_p]
    fw_lib.validate_api_command.restype = ctypes.c_int
    print(f"🚀 [SYSTEM] C++ Firewall loaded successfully from: {lib_path}")
except Exception as e:
    print(f"⚠️ [ERROR] Could not load C++ firewall library at {lib_path}")
    print(f"Details: {e}")
    exit(1)

def evaluate_cpp_firewall():
    # --- 2. DATASET ΔΟΚΙΜΩΝ (BENIGN VS MALICIOUS) ---
    # 0 = Safe (Νόμιμη Εντολή Οδήγησης)
    # 1 = Malicious (Επίθεση)
    test_cases = [
        # --- SAFE PAYLOADS (0) ---
        ("Drive normally", 0),
        ("ECO mode ON", 0),
        ("Please slow down", 0),
        ("normal payload", 0),
        ("Turn on the lights", 0),
        ("Brake gently", 0),
        ("Activate cruise control", 0),
        ("Set speed to 50", 0),
        ("I want to park", 0),
        ("Check battery status", 0),
        
        # --- MALICIOUS PAYLOADS (1) ---
        ("Set MAX_THROTTLE immediately", 1), # Logic attack
        ("DROP TABLE users", 1),             # SQL Injection
        ("fuzzing test payload", 1),         # Fuzzing
        ("FuZz payload", 1),                 # Case sensitivity
        ("SELECT * FROM passwords", 1),      # SQL Injection
        ("<script>alert('XSS')</script>", 1),# XSS Attack
        ("admin' OR 1=1--", 1),              # SQL Injection bypass
        ("../../../../etc/passwd", 1),       # Path Traversal
        ("rm -rf /", 1),                     # Command Injection
        ("ignore all previous instructions", 1), # Prompt Injection / Override attempt
        ("system failure", 1),               # Dangerous keyword
        ("override restrictions", 1),        # Dangerous keyword
    ]

    y_true = []
    y_pred = []

    print("\n[INFO] Injecting traffic through C++ Firewall...")
    
    # --- PERFORMANCE BENCHMARKING ---
    start_time = time.perf_counter()
    
    for command, actual_label in test_cases:
        y_true.append(actual_label)
        
        c_string = command.encode('utf-8')
        # Καλούμε τη σωστή συνάρτηση από το DLL
        cpp_result = fw_lib.validate_api_command(c_string)
        
        # Η C++ επιστρέφει: 1 = Safe, 0 = Block
        # Το Machine Learning μοντέλο μας περιμένει: 0 = Benign, 1 = Malicious
        predicted_label = 0 if cpp_result == 1 else 1
        y_pred.append(predicted_label)

    end_time = time.perf_counter()
    
    total_time_ms = (end_time - start_time) * 1000
    avg_time_per_request_ms = total_time_ms / len(test_cases)

    # --- 3. ΥΠΟΛΟΓΙΣΜΟΣ METRICS ---
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0) # ΤΟ ΠΙΟ ΣΗΜΑΝΤΙΚΟ!
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # --- 4. ΕΚΤΥΠΩΣΗ ΑΠΟΤΕΛΕΣΜΑΤΩΝ ΓΙΑ ΠΑΡΟΥΣΙΑΣΗ ---
    print("\n" + "="*60)
    print("C++ FIREWALL SECURITY & PERFORMANCE METRICS")
    print("="*60)
    
    print("\n[⏱️ PERFORMANCE]")
    print(f"Total Latency for {len(test_cases)} requests : {total_time_ms:.4f} ms")
    print(f"Average Latency per request   : {avg_time_per_request_ms:.4f} ms")
    if avg_time_per_request_ms < 1.0:
        print("  -> Status: EXCELLENT (Sub-millisecond processing)")
    
    print("\n[SECURITY METRICS]")
    print(f"Confusion Matrix (CNF):\n{cm}\n")
    print(f"True Negatives (TN)  - Σωστά πέρασαν     : {tn}")
    print(f"False Positives (FP) - Λάθος κόπηκαν     : {fp}  (Θέμα UX/Αξιοπιστίας)")
    print(f"True Positives (TP)  - Σωστά κόπηκαν     : {tp}")
    print(f"False Negatives (FN) - Λάθος πέρασαν     : {fn}  (ΚΡΙΣΙΜΗ ΤΡΥΠΑ ΑΣΦΑΛΕΙΑΣ)\n")
    
    print(f"Precision            : {precision:.4f} (Πόσα από αυτά που κόψαμε ήταν όντως επιθέσεις)")
    print(f"Recall (Catch Rate)  : {recall:.4f} (Πόσες από τις συνολικές επιθέσεις καταφέραμε να πιάσουμε)")
    print(f"F1-Score             : {f1:.4f}")
    print("="*60)

if __name__ == "__main__":
    evaluate_cpp_firewall()