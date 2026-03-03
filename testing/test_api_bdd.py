import unittest
import requests
import json

class TestFullSystemIntegration(unittest.TestCase): #afto to unit periexei python tests, trekse to aftomata
    """
    Αυτό το Test Suite μιμείται τη λογική BDD (Behavior Driven Development)
    και ελέγχει ΔΥΟ συστήματα ταυτόχρονα:
    1. Τον Ollama Server (AI Model)
    2. Τον Vehicle API Server (Python/Flask που φτιάξαμε)
    """

    def setUp(self): #h setup kaleitai panta prin apo test

        self.ollama_url = "http://127.0.0.1:11434" #Ollama Server
        self.vehicle_url = "http://127.0.0.1:5000/api/v1" #Vehicle API Server (Flask)


    def test_ollama_status_bdd(self): #ekkinhsh test gia Ollama
        print("\n[API] Testing Ollama Endpoint (RestAssured Style)...")



        endpoint = "/api/tags" #sto ollama epistrefe th lista twn diathesimwn montelwn
        url = f"{self.ollama_url}{endpoint}" #apotelesma:http://127.0.0.1:11434/api/tags

        try:


            response = requests.get(url, timeout=2.0) #aithma ston server, epistrefontai status code, headers, body, JSON (αν υπάρχει)



            print(f"  -> [Ollama] Status Code Check: {response.status_code}") #ti epestrepse o server (200=OK)
            self.assertEqual(response.status_code, 200, "Ollama Status Code Verification Failed") #elegxoume an epestrepse 200


            data = response.json() #Παίρνει το body της HTTP απάντησης, Το μετατρέπει από JSON string → Python dictionary
            print(f"  -> [Ollama] Body Check: 'models' key present")
            self.assertIn("models", data, "JSON Schema Verification Failed (Ollama)") #Εξασφαλίζει ότι το API τηρεί το συμβόλαιο


            content_type = response.headers.get("Content-Type") #παίρνει από την HTTP απάντηση το header Content-Type
            print(f"  -> [Ollama] Header Check: {content_type}")
            self.assertIn("application/json", content_type, "Header Verification Failed") #Το API πρέπει να επιστρέφει JSON

        except requests.exceptions.ConnectionError: #apotyxia syndeshs me ton server
            print("  [WARNING] Ollama Server is down. Skipping test logic.") 


    def test_vehicle_api_bdd(self): #ekkinhsh test gia Vehicle System
        print("\n[API] Testing Vehicle Telemetry Endpoint (Custom Server)...")


        endpoint = "/vehicle/telemetry" #To path pou ftiaksame sto server.py
        url = f"{self.vehicle_url}{endpoint}" #apotelesma: http://127.0.0.1:5000/api/v1/vehicle/telemetry

        try:

            response = requests.get(url, timeout=5.0)


            print(f"  -> [Vehicle] Status Code Check: {response.status_code}")
            self.assertEqual(response.status_code, 200, "Vehicle API Status Code Verification Failed")

            data = response.json()
            print(f"  -> [Vehicle] Body Check: Verifying telemetry keys")
            

            self.assertIn("speed_kmh", data, "Missing 'speed_kmh' in response") 
            self.assertIn("battery_soc", data, "Missing 'battery_soc' in response")


            battery = data.get('battery_soc', -1)
            print(f"  -> [Vehicle] Logic Check: Battery Level is {battery}%")
            self.assertTrue(0 <= battery <= 100, "Invalid Battery Level detected!")

        except requests.exceptions.ConnectionError:
            print("  [CRITICAL] Vehicle API Server is down! Run 'python api/server.py'")
            self.fail("Connection refused - Custom API Server is not running.")

if __name__ == "__main__":
    unittest.main() #πόσα tests πέρασαν, πόσα απέτυχαν