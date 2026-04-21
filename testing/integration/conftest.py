import subprocess, time, pytest

@pytest.fixture(scope='session', autouse=True)
def start_server():
    print('\n[SETUP] Starting Uvicorn test server...')
    proc = subprocess.Popen(['python', '-m', 'uvicorn', 'api_server:app', '--host', '127.0.0.1', '--port', '8000'])
    time.sleep(5)  # Wait for boot
    yield
    print('\n[TEARDOWN] Stopping Uvicorn test server...')
    proc.terminate()
