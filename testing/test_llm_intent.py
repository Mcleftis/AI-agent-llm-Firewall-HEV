import requests
import logging
import pytest

# ==========================================
# CONSTANTS (Τέλος τα Magic Numbers)
# ==========================================
HTTP_OK = 200
BASE_URL = "http://127.0.0.1:5000/api/v1"
TIMEOUT_SEC = 5.0

# ==========================================
# LOGGER SETUP (Τέλος οι απαγορευμένες 'print')
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# API INTEGRATION TESTS (Σε καθαρό Pytest)
# ==========================================

# Προστέθηκε το -> None (Type Hinting)
def test_health_check() -> None:
    """Ελέγχει αν το βασικό API είναι ζωντανό και υγιές."""
    logger.info("\n[TEST] Checking System Health Endpoint...")
    url = f"{BASE_URL}/system/health"
    
    try:
        response = requests.get(url, timeout=TIMEOUT_SEC)
        
        # Pytest 'assert' αντί για self.assertEqual
        assert response.status_code == HTTP_OK, f"Expected {HTTP_OK}, got {response.status_code}"
        
        data = response.json()
        logger.info(f"  -> Status: {data['status']}")
        
        assert data['status'] == "HEALTHY", f"System is in state: {data['status']}"
        assert data['modules']['api_server'] is True, "API server module reported as down"
        
    except requests.exceptions.ConnectionError:
        logger.error("❌ Το app.py δεν τρέχει! (Connection Refused)")
        # Κόβουμε το test βίαια και επίσημα μέσω του framework
        pytest.fail("Connection refused - System API is unreachable.")


def test_intent_analysis() -> None:
    """Ελέγχει αν ο LLM Agent αναγνωρίζει σωστά την πρόθεση του οδηγού."""
    logger.info("\n[TEST] Checking LLM Driver Intent Endpoint...")
    url = f"{BASE_URL}/driver/intent"
    payload = {"command": "I am rushing to the hospital"}
    
    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT_SEC)
        
        assert response.status_code == HTTP_OK, f"Expected {HTTP_OK}, got {response.status_code}"
        
        data = response.json()
        analysis = data['analysis']
        
        logger.info(f"  -> Input: '{payload['command']}'")
        logger.info(f"  -> Result Mode: {analysis.get('mode')}")
        
        # Ελέγχουμε την επιχειρησιακή λογική (Business Logic)
        assert analysis.get('mode') == "SPORT", "Ο LLM Agent απέτυχε να γυρίσει το αμάξι σε SPORT mode σε κατάσταση έκτακτης ανάγκης"
        
    except requests.exceptions.ConnectionError:
        logger.error("❌ Το app.py δεν τρέχει! (Connection Refused)")
        pytest.fail("Connection refused - Intent API is unreachable.")