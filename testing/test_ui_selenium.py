import unittest
import requests

class TestHevApp(unittest.TestCase):
    
    def setUp(self):

        self.base_url = "http://127.0.0.1:5000/api/v1"

    def test_health_check(self):
        print("\n[TEST] Checking System Health Endpoint...")
        url = f"{self.base_url}/system/health"
        
        try:
            response = requests.get(url)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            print(f"  -> Status: {data['status']}")
            self.assertEqual(data['status'], "HEALTHY")
            self.assertTrue(data['modules']['api_server'])
            
        except requests.exceptions.ConnectionError:
            print("❌ Το app.py δεν τρέχει! (Άνοιξε το σε άλλο τερματικό)")
            self.fail("Connection refused")

    def test_intent_analysis(self):
        print("\n[TEST] Checking LLM Driver Intent Endpoint...")
        url = f"{self.base_url}/driver/intent"
        payload = {"command": "I am rushing to the hospital"}
        
        try:
            response = requests.post(url, json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            
            analysis = data['analysis']
            print(f"  -> Input: '{payload['command']}'")
            print(f"  -> Result Mode: {analysis.get('mode')}")
            

            self.assertEqual(analysis.get('mode'), "SPORT")
            
        except requests.exceptions.ConnectionError:
            self.fail("App not running")

if __name__ == "__main__":
    unittest.main()