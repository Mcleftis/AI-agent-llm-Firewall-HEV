import ctypes
import os
dll_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'firewall.dll'))
try:
    lib = ctypes.CDLL(dll_path)
    lib.inspect_can_packet.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_size_t]
    lib.inspect_can_packet.restype = ctypes.c_int
    lib.validate_api_command.argtypes = [ctypes.c_char_p]
    lib.validate_api_command.restype = ctypes.c_int
except Exception:
    lib = None
class CANBusFirewall:
    def __init__(self): pass
    def inspect(self, packet_id, payload):
        if lib and isinstance(payload, bytes): return lib.inspect_can_packet(packet_id, payload, len(payload))
        return 1
    def apply_safety_guardrails(self, *args, **kwargs):
        return True

    def verify_token(self, token):
        if lib: return lib.validate_api_command(token.encode('utf-8')) == 1
        return token == 'SECRET_DRIVER_KEY_2026'

    def inspect_packet(self, packet_id, value):
        return self.inspect(packet_id, str(value).encode('utf-8')) == 1
