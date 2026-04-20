import pytest
from cpp_firewall.hev_idps_bridge import CANBusFirewall

class TestCANBusSecurity:

    
    @pytest.fixture
    def firewall(self):
        return CANBusFirewall(max_delta=50, max_packets=20)

    
    def test_authentication_rejection(self, firewall):
        """Ελέγχει αν το firewall μπλοκάρει άγνωστα/hacker tokens."""
        hacker_token = "HACKER_123"
        
        
        assert not firewall.verify_token(hacker_token), "CRITICAL: Firewall allowed unauthorized hacker access!"

    def test_authentication_acceptance(self, firewall):
        """Ελέγχει αν το firewall επιτρέπει τα σωστά tokens."""
        driver_token = "SECRET_DRIVER_KEY_2026"
        
        assert firewall.verify_token(driver_token), "CRITICAL: Firewall blocked a valid driver token!"

    
    def test_spoofing_teleport_check(self, firewall):
        """Ελέγχει αν το firewall κόβει αφύσικα άλματα στις τιμές των αισθητήρων (max_delta)."""
        packet_id = 0x100
        
        
        firewall.inspect_packet(packet_id, "50.0")
        
        
        is_safe = firewall.inspect_packet(packet_id, "200.0")
        
        
        assert not is_safe, "CRITICAL: Firewall failed to detect speed spoofing (Delta limit bypassed)!"

    
    def test_dos_flooding_mitigation(self, firewall):
        """Ελέγχει αν το firewall κόβει το spamming πακέτων μετά το όριο max_packets."""
        blocked_count = 0
        
        
        for i in range(50):
            is_safe = firewall.inspect_packet(0x100, str(50 + i))
            if not is_safe:
                blocked_count += 1
                
        
        assert blocked_count >= 30, f"CRITICAL: DoS Attack Successful! Only {blocked_count}/50 packets blocked."