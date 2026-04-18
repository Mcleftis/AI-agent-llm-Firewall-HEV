import unittest
import requests
import logging  # Αντικαθιστά την print()

# Ορισμός Logger για καθαρά CI/CD logs
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- ΕΠΙΛΥΣΗ "MAGIC NUMBERS" ---
HTTP_OK = 200
TIMEOUT_OLLAMA = 2.0
TIMEOUT_VEHICLE = 5.0
BATTERY_MIN = 0
BATTERY_MAX = 100
# -------------------------------

class TestFullSystemIntegration(unittest.TestCase):
    """
    Αυτό το Test Suite μιμείται τη λογική BDD (Behavior Driven Development)
    και ελέγχει ΔΥΟ συστήματα ταυτόχρονα:
    1. Τον Ollama Server (AI Model)
    2. Τον Vehicle API Server (Python/Flask που φτιάξαμε)
    """

    # ΕΠΙΛΥΣΗ TYPE HINTS: Προσθήκη -> None
    def setUp(self) -> None: 
        self.ollama_url = "http://127.0.0.1:11434" 
        self.vehicle_url = "http://127.0.0.1:5000/api/v1" 

    def test_ollama_status_bdd(self) -> None:
        # ΕΠΙΛΥΣΗ PRINT: Αντικατάσταση με logger.info
        logger.info("\n[API] Testing Ollama Endpoint (RestAssured Style)...")

        endpoint = "/api/tags" 
        url = f"{self.ollama_url}{endpoint}" 

        try:
            # ΕΠΙΛΥΣΗ MAGIC NUMBER: 2.0 -> TIMEOUT_OLLAMA
            response = requests.get(url, timeout=TIMEOUT_OLLAMA) 

            logger.info(f"  -> [Ollama] Status Code Check: {response.status_code}")
            # ΕΠΙΛΥΣΗ MAGIC NUMBER: 200 -> HTTP_OK
            self.assertEqual(response.status_code, HTTP_OK, "Ollama Status Code Verification Failed") 

            data = response.json() 
            logger.info("  -> [Ollama] Body Check: 'models' key present")
            self.assertIn("models", data, "JSON Schema Verification Failed (Ollama)") 

            content_type = response.headers.get("Content-Type") 
            logger.info(f"  -> [Ollama] Header Check: {content_type}")
            self.assertIn("application/json", content_type, "Header Verification Failed") 

        except requests.exceptions.ConnectionError: 
            # Χρήση warning αντί για απλό print
            logger.warning("  [WARNING] Ollama Server is down. Skipping test logic.") 

    def test_vehicle_api_bdd(self) -> None:
        logger.info("\n[API] Testing Vehicle Telemetry Endpoint (Custom Server)...")

        endpoint = "/vehicle/telemetry" 
        url = f"{self.vehicle_url}{endpoint}" 

        try:
            # ΕΠΙΛΥΣΗ MAGIC NUMBER: 5.0 -> TIMEOUT_VEHICLE
            response = requests.get(url, timeout=TIMEOUT_VEHICLE)

            logger.info(f"  -> [Vehicle] Status Code Check: {response.status_code}")
            # ΕΠΙΛΥΣΗ MAGIC NUMBER: 200 -> HTTP_OK
            self.assertEqual(response.status_code, HTTP_OK, "Vehicle API Status Code Verification Failed")

            data = response.json()
            logger.info("  -> [Vehicle] Body Check: Verifying telemetry keys")
            
            self.assertIn("speed_kmh", data, "Missing 'speed_kmh' in response") 
            self.assertIn("battery_soc", data, "Missing 'battery_soc' in response")

            battery = data.get('battery_soc', -1)
            logger.info(f"  -> [Vehicle] Logic Check: Battery Level is {battery}%")
            
            # ΕΠΙΛΥΣΗ MAGIC NUMBERS: 0 και 100 -> BATTERY_MIN, BATTERY_MAX
            self.assertTrue(BATTERY_MIN <= battery <= BATTERY_MAX, "Invalid Battery Level detected!")

        except requests.exceptions.ConnectionError:
            # Χρήση error αντί για print
            logger.error("  [CRITICAL] Vehicle API Server is down! Run 'python api/server.py'")
            self.fail("Connection refused - Custom API Server is not running.")

if __name__ == "__main__":
    unittest.main()