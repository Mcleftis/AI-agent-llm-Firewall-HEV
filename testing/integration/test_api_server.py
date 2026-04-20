import time
import requests

# Το API σου τρέχει στην 8000 βάσει του api_server.py
BASE_URL = "http://127.0.0.1:8000"

class TestAPIServer:
    
    def test_server_health(self):
        """Ελέγχει αν ο server έχει σηκωθεί και απαντάει στο /health."""
        print("\n[TEST] Pinging API Server...")
        max_retries = 5
        server_up = False
        
        for i in range(max_retries):
            try:
                response = requests.get(f"{BASE_URL}/health", timeout=2)
                if response.status_code == 200:
                    server_up = True
                    break
            except requests.exceptions.ConnectionError:
                print(f" -> Retry {i+1}/{max_retries}...")
                time.sleep(1)
                
        assert server_up, "CRITICAL: API Server is dead (Connection Refused)."

    def test_waf_security_middleware(self):
        """[DEVSECOPS] Ελέγχει αν το WAF κόβει κακόβουλα Path Traversal requests."""
        # Προσομοιώνουμε έναν Hacker που πάει να κλέψει το .env αρχείο σου
        malicious_url = f"{BASE_URL}/.env"
        
        response = requests.get(malicious_url)
        
        # Περιμένουμε το middleware σου να ρίξει πόρτα (403 Forbidden)
        assert response.status_code == 403, f"SECURITY BREACH! WAF failed. Got status: {response.status_code}"
        assert "Security Exception" in response.json().get("detail", ""), "WAF did not return the expected block message!"