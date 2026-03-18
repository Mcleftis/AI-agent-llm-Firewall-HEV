import ctypes
import os

class VehicleState(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('current_speed_kmh', ctypes.c_float),
        ('requested_throttle', ctypes.c_float),
        ('requested_brake', ctypes.c_float),
        ('battery_soc', ctypes.c_float),
        ('battery_temp_celsius', ctypes.c_float),
        ('engine_temperature_celsius', ctypes.c_float),
        ('motor_temp_celsius', ctypes.c_float),
        ('gear_position', ctypes.c_int32)
    ]

# Load DLL
dll_path = os.path.join(os.path.dirname(__file__), 'firewall.dll')
try:
    lib = ctypes.CDLL(dll_path)
    
    # Setup apply_safety_guardrails
    lib.apply_safety_guardrails.argtypes = [ctypes.POINTER(VehicleState)]
    lib.apply_safety_guardrails.restype = ctypes.c_bool
    
    # Setup get_idps_version
    lib.get_idps_version.argtypes = []
    lib.get_idps_version.restype = ctypes.c_char_p
    
    print(f"? Loaded C++ IDPS Version: {lib.get_idps_version().decode('utf-8')}")
except OSError:
    print("? Cannot find firewall.dll. Did you run the build script?")
    lib = None

def apply_guardrails(state: VehicleState) -> bool:
    if lib:
        return lib.apply_safety_guardrails(ctypes.byref(state))
    return False

if __name__ == '__main__':
    # Test Hallucination: Full Throttle + Full Brake
    test_state = VehicleState(current_speed_kmh=100.0, requested_throttle=1.0, requested_brake=1.0, battery_soc=50.0)
    print(f"[*] BEFORE: Throttle={test_state.requested_throttle}, Brake={test_state.requested_brake}")
    
    was_safe = apply_guardrails(test_state)
    
    print(f"[*] AFTER:  Throttle={test_state.requested_throttle}, Brake={test_state.requested_brake}")
    print(f"[*] VERDICT: {'? SAFE' if was_safe else '?? IDPS INTERVENED'}")
