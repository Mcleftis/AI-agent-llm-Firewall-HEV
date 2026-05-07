import sys
import os
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MIN_REQUIRED_ARGS = 2


def run_script(path_parts: list[str]) -> None:
    """Βοηθητική συνάρτηση για να τρέχει scripts σωστά σε Windows/Linux"""
    script_path = os.path.join(BASE_DIR, *path_parts)

    if not os.path.exists(script_path):
        print(f"Error: Το αρχείο {script_path} δεν βρέθηκε!")
        return

    print(f"Running: {path_parts[-1]}...")
    try:
        subprocess.run([sys.executable, script_path], check=True)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"\nError occurred (Code {e.returncode}).")


def _run_sim() -> None:
    """Selects the correct simulation entry point based on what exists on disk."""
    if os.path.exists(os.path.join(BASE_DIR, "main.py")):
        run_script(["main.py"])
    else:
        run_script(["full_system.py"])


COMMANDS: dict[str, object] = {
    "init": lambda: run_script(["api", "init_db.py"]),
    "run":  lambda: run_script(["api", "server.py"]),
    "sim":  _run_sim,
    "test": lambda: run_script(["test_db.py"]),
}


def main() -> None:
    if len(sys.argv) < MIN_REQUIRED_ARGS:
        print("Usage: python manage.py [init|run|sim|test]")
        print("   init  -> Initialize Database")
        print("   run   -> Run API Server")
        print("   sim   -> Run Vehicle Simulation")
        print("   test  -> Test Database Connection")
        return

    command = sys.argv[1]
    handler = COMMANDS.get(command)

    if handler is None:
        print(f"Unknown command: {command}")
        return

    handler()


if __name__ == "__main__":
    main()