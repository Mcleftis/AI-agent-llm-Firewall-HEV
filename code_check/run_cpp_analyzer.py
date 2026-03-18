import os
import re
import ctypes
import random
import string
import time
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
#  STATIC ANALYSIS RULES (Regex Based για C++)
# ═══════════════════════════════════════════════════════════════════════════════

_DANGEROUS_C_FUNCTIONS = {
    "strcpy": "Buffer overflow risk — use strncpy or std::string",
    "gets": "Fatal buffer overflow risk — removed in C++14 — use std::getline",
    "sprintf": "Buffer overflow risk — use snprintf or std::ostringstream",
    "system": "OS Command Injection risk",
    "rand": "Weak PRNG — use <random> (std::mt19937)",
    "strlen": "Can crash if string is not null-terminated",
}

_SECRET_PATTERNS = [
    ("AWS Access Key",      re.compile(r"(?<![A-Z0-9])(AKIA|ASIA|AROA)[A-Z0-9]{16}(?![A-Z0-9])")),
    ("GitHub Token",        re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}")),
    ("Generic API Token",   re.compile(r"(?i)(api[_\-]?key|token|secret)['\"]?\s*[:=]\s*['\"]([A-Za-z0-9\-_]{20,})['\"]")),
    ("Hardcoded Password",  re.compile(r"(?i)(password|passwd|pwd)\s*=\s*['\"](?!.*\{)[^'\"]{6,}['\"]")),
]

_FUNC_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*\{?")

# ═══════════════════════════════════════════════════════════════════════════════
#  PART 1: STATIC CODE ANALYSIS (Parser)
# ═══════════════════════════════════════════════════════════════════════════════

class CppStaticAnalyzer:
    def __init__(self):
        self.file_issues = defaultdict(list)
        self.func_issues = defaultdict(lambda: defaultdict(list))
        self.total_spaghetti = 0

    def scan_file(self, filepath: str):
        filename = os.path.basename(filepath)
        
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except Exception:
            return

        in_function = False
        current_func_name = ""
        func_start_line = 0
        bracket_count = 0
        
        for i, line in enumerate(lines):
            lineno = i + 1
            clean_line = line.strip()
            
            # --- 1. Secret Scanning ---
            for label, pattern in _SECRET_PATTERNS:
                if pattern.search(line):
                    self.file_issues[filename].append(f"🔑 Secret Scanning [γραμμή {lineno}]: {label} detected in string literal")

            # --- 2. Dangerous Functions ---
            for bad_func, reason in _DANGEROUS_C_FUNCTIONS.items():
                if re.search(r"\b" + bad_func + r"\s*\(", line):
                    self.file_issues[filename].append(f"⛔ SAST Hotspot [γραμμή {lineno}]: '{bad_func}' — {reason}")

            # --- 3. Magic Numbers (Απλοϊκό Regex) ---
            if re.search(r"=\s*\d{2,}\b|\b==\s*\d{2,}\b|\b[<>]\s*\d{2,}\b", clean_line):
                if not clean_line.startswith("#") and "const" not in clean_line:
                     self.file_issues[filename].append(f"🔢 Magic Number [γραμμή {lineno}]: Hardcoded number detected -> {clean_line[:30]}...")

            # --- 4. God Function Detector ---
            if not in_function:
                match = _FUNC_REGEX.match(clean_line)
                if match and not clean_line.endswith(";"):
                    in_function = True
                    current_func_name = match.group(0).split("(")[0].split()[-1]
                    func_start_line = lineno
                    bracket_count = line.count("{") - line.count("}")
            else:
                bracket_count += line.count("{") - line.count("}")
                if bracket_count <= 0:
                    func_length = lineno - func_start_line
                    if func_length > 50:
                        self.func_issues[filename][current_func_name].append(f"God Function [γραμμές {func_start_line}–{lineno}]: Τεράστια συνάρτηση ({func_length} γραμμές).")
                        self.total_spaghetti += 1
                    
                    in_function = False
                    current_func_name = ""

# ═══════════════════════════════════════════════════════════════════════════════
#  PART 2: DYNAMIC ANALYSIS (Fuzzing via ctypes)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_junk_string(length):
    letters = string.ascii_letters + string.punctuation + " \n\t"
    return ''.join(random.choice(letters) for i in range(length))

def run_dynamic_fuzzer(project_root: str):
    print(f"\n{'=' * 60}")
    print("🔥 DYNAMIC ANALYSIS: FUZZING & MEMORY STRESS TEST 🔥")
    print("Σκοπός: Δοκιμή Memory Leaks / Buffer Overflows στο Firewall DLL")
    print("=" * 60)

    lib_extension = ".dll" if os.name == "nt" else ".so"
    lib_path = os.path.join(project_root, "cpp_firewall", f"firewall{lib_extension}")

    if not os.path.exists(lib_path):
        print(f"⚠️ [FUZZER] Παράλειψη Dynamic Test. Δεν βρέθηκε το DLL στο: {lib_path}")
        return

    try:
        fw_lib = ctypes.CDLL(lib_path)
        fw_lib.validate_command.argtypes = [ctypes.c_char_p]
        fw_lib.validate_command.restype = ctypes.c_int
        print(f"🚀 [FUZZER] DLL Loaded: {lib_path}\n")
    except Exception as e:
        print(f"❌ [FUZZER] Αποτυχία φόρτωσης DLL: {e}")
        return

    # ΤΕΣΤ 1: Buffer Overflows
    print("[TEST 1] Βομβαρδισμός με τεράστια Strings (10,000 chars)...")
    try:
        for _ in range(10):
            huge_payload = generate_junk_string(10000).encode('utf-8')
            fw_lib.validate_command(huge_payload)
        print("  ✅ [PASS] Δεν εντοπίστηκε Buffer Overflow.")
    except Exception as e:
        print(f"  ❌ [FAIL] Πιθανό Buffer Overflow. Η C++ κράσαρε: {e}")

    # ΤΕΣΤ 2: Null Pointer / Type Confusion
    print("\n[TEST 2] Δοκιμή με επικίνδυνους χαρακτήρες (Null bytes, Unicode)...")
    dangerous_payloads = [
        b"",
        b"A" * 5000,
        b"DROP \x00 TABLE",
        b"\xff\xfe\xfd\xfc",
        b"Select * from \n\r\t"
    ]
    try:
        for payload in dangerous_payloads:
            fw_lib.validate_command(payload)
        print("  ✅ [PASS] Διαχείριση επικίνδυνων bytes επιτυχής.")
    except Exception as e:
        print(f"  ❌ [FAIL] Η C++ κράσαρε σε περίεργο payload: {e}")

    # ΤΕΣΤ 3: Memory Leaks
    print("\n[TEST 3] Stress Test Memory Leaks (100,000 κλήσεις)...")
    start_time = time.time()
    try:
        for _ in range(100000):
            fw_lib.validate_command(b"test string")
        
        duration = time.time() - start_time
        print(f"  ✅ [PASS] Η C++ επέζησε από 100,000 κλήσεις σε {duration:.2f} s.")
        print("            (Αν υπήρχε serious leak, το process θα είχε καταρρεύσει)")
    except Exception as e:
        print(f"  ❌ [FAIL] Κατάρρευση μνήμης κατά τη διάρκεια του Stress Test: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_hybrid_analysis(project_root: str):
    print(f"'Hybrid C++ CodeCheck' (Enterprise Mode — v3.0)\n{'=' * 60}")
    
    # 1. STATIC ANALYSIS
    analyzer = CppStaticAnalyzer()
    files_checked = 0
    
    for root, dirs, files in os.walk(project_root):
        if any(bad in root for bad in [".git", "build", "out", "venv", "__pycache__"]):
            continue
            
        for file in files:
            if file.endswith((".cpp", ".c", ".h", ".hpp")):
                file_path = os.path.join(root, file)
                analyzer.scan_file(file_path)
                files_checked += 1

    all_affected_files = set(analyzer.file_issues.keys()).union(set(analyzer.func_issues.keys()))
    
    for file in all_affected_files:
        print(f"\n🚨 Αρχείο: {file}")
        
        for issue in analyzer.file_issues.get(file, []):
            print(f"   ⚠️  [FILE LEVEL]: {issue}")
            
        for func_name, issues in analyzer.func_issues.get(file, {}).items():
            print(f"   ❌ Συνάρτηση '{func_name}()':")
            for issue in issues:
                print(f"      - {issue}")
        print("-" * 60)

    print(f"\n📊 STATIC SUMMARY: Ελέγχθηκαν {files_checked} αρχεία C/C++.")
    if len(all_affected_files) == 0:
        print("✅ STATIC ΑΠΟΤΕΛΕΣΜΑ: Πεντακάθαρος κώδικας.")
    else:
        print(f"⚠️  STATIC ΑΠΟΤΕΛΕΣΜΑ: Βρέθηκαν ζητήματα σε {len(all_affected_files)} αρχεία.")

    # 2. DYNAMIC ANALYSIS
    run_dynamic_fuzzer(project_root)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    thesis_dir = os.path.dirname(script_dir)
    run_hybrid_analysis(thesis_dir)