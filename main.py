import argparse
import logging
import sys
import os
import hashlib
from typing import Callable

try:
    from profiling import measure_performance
except ImportError:
    def measure_performance(func: Callable) -> Callable:
        return func

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- CONSTANTS (No more Magic Numbers) ---
CHUNK_SIZE    = 4096
DEFAULT_STEPS = 100000
DEFAULT_LR    = 0.0003

# ==========================================
# SECURITY HELPERS
# ==========================================

def _calculate_file_hash(file_path: str) -> str:
    """Βοηθητική συνάρτηση για τον υπολογισμό του hash."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(CHUNK_SIZE), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def verify_model_integrity(model_path_prefix: str) -> bool:
    """Ελέγχει αν το αρχείο του μοντέλου (.zip) ταιριάζει με την υπογραφή (.sha256)."""
    model_file = f"{model_path_prefix}.zip"
    hash_file  = f"{model_path_prefix}.sha256"

    if not os.path.exists(model_file):
        logging.error(f"[SECURITY] Model file missing: {model_file}")
        return False

    if not os.path.exists(hash_file):
        logging.critical("[SECURITY BLOCK] Cannot verify integrity. System Halted.")
        return False

    calculated_hash = _calculate_file_hash(model_file)

    with open(hash_file, "r") as f:
        expected_hash = f.read().strip()

    if calculated_hash == expected_hash:
        logging.info("[SECURITY] Integrity Verified. Model is authentic.")
        return True

    logging.critical("[SECURITY ALERT] HASH MISMATCH! The model file has been altered/hacked.")
    logging.critical(f"Expected: {expected_hash}")
    logging.critical(f"Actual:   {calculated_hash}")
    return False

def _ensure_security(model_path: str) -> None:
    """DRY Helper: Ελέγχει την ασφάλεια και τερματίζει το πρόγραμμα αν αποτύχει."""
    logging.info("Performing Security Scan on Model...")
    if not verify_model_integrity(model_path):
        sys.exit(1)

# ==========================================
# MODE HANDLERS
# ==========================================

def run_train(args: argparse.Namespace) -> None:
    from AI_agent import train_ppo
    logging.info("Starting PPO Training...")
    measured_train = measure_performance(train_ppo)
    measured_train(steps=args.steps, lr=args.lr, traffic=args.traffic)
    logging.info("Training Done.")

def run_demo(args: argparse.Namespace) -> None:
    _ensure_security(args.model_path)
    from full_system import run_live_system
    logging.info("Initializing Live Demo...")
    measured_demo = measure_performance(run_live_system)
    measured_demo(prompt=args.driver_mood, model_path=args.model_path)

def run_evaluate(args: argparse.Namespace) -> None:
    _ensure_security(args.model_path)
    from evaluate_agent import run_evaluation
    run_evaluation(model_path=args.model_path)

def run_optimize(args: argparse.Namespace) -> None:
    from optimize import run_grid_search
    logging.info("Starting Grid Search...")
    measured_opt = measure_performance(run_grid_search)
    measured_opt()

def run_ablation(args: argparse.Namespace) -> None:
    from run_ablation import run_study
    logging.info("Running Ablation Study...")
    measured_ablation = measure_performance(run_study)
    measured_ablation()

# ==========================================
# MAIN CLI
# ==========================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Neuro-Symbolic HEV Control System CLI")
    parser.add_argument('--mode', type=str, choices=['train', 'evaluate', 'demo', 'ablation', 'optimize'], required=True)
    parser.add_argument('--steps', type=int, default=DEFAULT_STEPS, help='Training steps')
    parser.add_argument('--lr', type=float, default=DEFAULT_LR, help='Learning rate')
    parser.add_argument('--traffic', type=str, default='normal', choices=['low', 'normal', 'heavy'])
    parser.add_argument('--driver_mood', type=str, default='neutral', help='Prompt for Demo')
    parser.add_argument('--model_path', type=str, default='models/ppo_hev', help='Model file path (without .zip)')
    return parser.parse_args()

def main() -> None:
    args = parse_arguments()
    logging.info(f"Starting System in [{args.mode.upper()}] mode")

    mode_handlers: dict[str, Callable[[argparse.Namespace], None]] = {
        'train':    run_train,
        'demo':     run_demo,
        'evaluate': run_evaluate,
        'optimize': run_optimize,
        'ablation': run_ablation,
    }

    try:
        handler = mode_handlers.get(args.mode)
        if handler:
            handler(args)
    except ImportError as e:
        logging.error(f"Could not import module: {e}")
        logging.error("Tip: Ensure all files are in the same folder.")
    except Exception as e:
        logging.error(f"Critical Error during execution: {e}", exc_info=True)

if __name__ == "__main__":
    main()