import pytest
from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)

class TestAPIServer:
    def test_server_health(self):
        response = client.get('/health')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'

    def test_waf_security_middleware(self):
        response = client.get('/.env')
        assert response.status_code == 403
