import time
import logging
import os
import secrets
import struct
import ctypes
from typing import Dict
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- GLOBAL CONSTANTS ---
DEFAULT_RATE_LIMIT: int = 100
DEFAULT_BURST_LIMIT: int = 10

# --- ΦΟΡΤΩΣΗ ΤΗΣ C++ ΜΗΧΑΝΗΣ (DLL) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DLL_PATH = os.path.join(BASE_DIR, "cpp_firewall", "firewall.dll")

CPP_FIREWALL_AVAILABLE = False
try:
    c_firewall = ctypes.CDLL(DLL_PATH)

    # Ορισμός τύπων για το inspect_packet
    c_firewall.inspect_packet.argtypes = [ctypes.c_uint32, ctypes.c_char_p]
    c_firewall.inspect_packet.restype = ctypes.c_int

    # Ορισμός τύπων για το validate_command
    c_firewall.validate_command.argtypes = [ctypes.c_char_p]
    c_firewall.validate_command.restype = ctypes.c_int

    CPP_FIREWALL_AVAILABLE = True
    logging.info("🚀 [SECURITY] C++ Firewall Core Loaded Successfully!")
except OSError:
    logging.error(f"⚠️ [SECURITY ERROR] C++ DLL not found at {DLL_PATH}. Please compile firewall.cpp!")


# --- ΕΞΑΓΩΓΗ ΣΥΝΑΡΤΗΣΗΣ ΓΙΑ ΤΟ SERVER.PY ---
def validate_command(command: str) -> bool:
    """Ελέγχει αν μια εντολή από το API είναι ασφαλής μέσω C++."""
    if not CPP_FIREWALL_AVAILABLE:
        return True  # Αν δεν υπάρχει το DLL, περνάει (Fallback)
    is_safe = c_firewall.validate_command(command.encode('utf-8'))
    return bool(is_safe)


class CANBusFirewall:
    def __init__(self, rate_limit: int = DEFAULT_RATE_LIMIT, burst_limit: int = DEFAULT_BURST_LIMIT) -> None:
        self.auth_token: str = os.getenv("CAN_AUTH_TOKEN", "DEFAULT_SECURE_TOKEN")
        self.blocked_ids: set = set()

        # Token Bucket State
        self.rate_limit = rate_limit
        self.burst_limit = burst_limit
        self.buckets: Dict[int, Dict[str, float]] = {}

    def verify_token(self, input_token: str) -> bool:
        if not input_token:
            return False
        if secrets.compare_digest(input_token, self.auth_token):
            return True
        logging.critical("ACCESS DENIED: Auth Failed.")
        return False

    def _check_rate_limit(self, packet_id: int) -> bool:
        current_time = time.time()
        if packet_id not in self.buckets:
            self.buckets[packet_id] = {'tokens': self.burst_limit, 'last_check': current_time}

        bucket = self.buckets[packet_id]
        time_passed = current_time - bucket['last_check']
        new_tokens = time_passed * self.rate_limit
        bucket['tokens'] = min(bucket['tokens'] + new_tokens, self.burst_limit)
        bucket['last_check'] = current_time

        if bucket['tokens'] >= 1.0:
            bucket['tokens'] -= 1.0
            return True
        return False

    def _cpp_check(self, packet_id: int, payload: bytes) -> bool:
        if not CPP_FIREWALL_AVAILABLE:
            return True
        try:
            if c_firewall.inspect_packet(packet_id, payload):
                return True
            logging.warning(f"SEC ALERT: ID {hex(packet_id)} blocked by C++.")
        except Exception as e:
            logging.error(f"FIREWALL ERROR: {e}")
        return False

    def inspect_packet(self, packet_id: int, payload: bytes) -> bool:
        if packet_id in self.blocked_ids:
            return False
            
        if not self._check_rate_limit(packet_id):
            logging.error(f"DoS ATTACK: ID {hex(packet_id)} rate limited.")
            return False
            
        return self._cpp_check(packet_id, payload)
    
    def create_valid_packet(self, value: float, counter: int) -> bytes:
        """Δημιουργεί ένα έγκυρο Secure CAN Frame (8 bytes)."""
        return struct.pack('<fI', value, counter)