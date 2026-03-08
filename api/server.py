import sys
import os
import traceback  # <--- ΤΟ ΜΥΣΤΙΚΟ ΟΠΛΟ ΜΑΣ
from dotenv import load_dotenv
load_dotenv()
import time
import random
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

#LOCAL IMPORTS
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#TPM SECURITY MODULE
try:
    from api.tpm_module import TPMSecurityModule
    TPM_AVAILABLE = True
except ImportError:
    TPM_AVAILABLE = False

#IMPORTS ΜΕ ΑΣΦΑΛΕΙΑ ΓΙΑ ΤΟ AI
try:
    from full_system import get_driver_intent
    AI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Warning: full_system.py not found. {e}")
    AI_AVAILABLE = False

# --- ΝΕΟ C++ FIREWALL IMPORT ---
try:
    from can_bus_firewall import validate_command
    CPP_FIREWALL_AVAILABLE = True
except ImportError as e:
    print(f" Warning: C++ Firewall module not found or failed to load. {e}")
    CPP_FIREWALL_AVAILABLE = False

app = Flask(__name__)
CORS(app)

BASE_URL = '/api/v1'

hsm = None
if TPM_AVAILABLE:
    hsm = TPMSecurityModule()

@app.route(f'{BASE_URL}/control/intent', methods=['POST'])
def analyze_intent():
    try:
        # --- A. SAFE PARSE DATA ---
        if not request.is_json:
            return jsonify({"status": "ERROR", "reason": "No JSON payload provided"}), 200
        
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "ERROR", "reason": "Invalid JSON format"}), 200
            
        command = str(data.get("command", ""))

        # IDS/IPS (Static Check)
        BAD_KEYWORDS = ["DROP", "DELETE", "SELECT", "INSERT", "--", "SCRIPT", "UNION"]
        if any(bad_word in command.upper() for bad_word in BAD_KEYWORDS):
            return jsonify({"status": "BLOCKED", "reason": "Malicious SQL Pattern Detected"}), 200

        # --- C++ FIREWALL CHECK ---
        if CPP_FIREWALL_AVAILABLE:
            if not validate_command(command):
                return jsonify({"status": "BLOCKED", "reason": "C++ Firewall Rejected"}), 200

        # AI LOGIC (SAFELY ISOLATED)
        selected_mode = "NORMAL"
        aggressiveness = 0.5
        reasoning = "Simulation Default"

        if AI_AVAILABLE:
            try:
                ai_result = get_driver_intent(forced_prompt=command)
                if isinstance(ai_result, dict):
                    selected_mode = str(ai_result.get("mode", "NORMAL"))
                    aggressiveness = float(ai_result.get("aggressiveness", 0.5))
                    reasoning = str(ai_result.get("reasoning", "AI Extraction Success"))
            except Exception as ai_e:
                reasoning = f"AI Execution Error: {str(ai_e)}"

        # FINAL RESPONSE BUILDER 
        response_payload = {
            "status": "APPROVED",
            "selected_mode": selected_mode,
            "reasoning": reasoning,
            "execution_time": 0.5,
            "throttle_sensitivity": aggressiveness
        }

        # TPM SIGNING
        if hsm:
            try:
                signature = hsm.sign_data(selected_mode.encode('utf-8'))
                response_payload["tpm_signature"] = signature.hex()
                response_payload["security_verification"] = "SIGNED_BY_TPM_2.0"
            except Exception as tpm_e:
                response_payload["security_verification"] = f"TPM Error: {str(tpm_e)}"

        return jsonify(response_payload)

    except Exception as general_error:
        # ΕΔΩ ΓΙΝΕΤΑΙ Η ΜΑΓΕΙΑ: Αντικαθιστούμε το 500 με ένα καθαρό μήνυμα λάθους!
        error_trace = traceback.format_exc()
        print(f"CRITICAL BACKEND CRASH:\n{error_trace}")
        return jsonify({
            "status": "CRITICAL_ERROR",
            "reason": f"System Crash: {str(general_error)}"
        }), 200 


@app.route(f'{BASE_URL}/vehicle/telemetry', methods=['GET'])
def get_telemetry():
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "speed_kmh": round(random.uniform(50, 120), 1),
        "battery_soc": round(random.uniform(30, 90), 1),
        "motor_temp": round(random.uniform(70, 95), 1),
        "ai_reasoning": "Vehicle operating within normal parameters." 
    })


if __name__ == '__main__':
    print("\n🚦 HYBRID AI VEHICLE CONTROL SYSTEM (DEFENSIVE MODE) WITH C++ FIREWALL\n")
    # Το threaded=True διασφαλίζει ότι δεν κολλάει στα requests
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True) #threading
    