import sqlite3
import pytest
from typing import Generator

# Σταθερές
IDX_USER = 1
IDX_ACTION = 2

@pytest.fixture
def mock_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Δημιουργεί μια IN-MEMORY βάση δεδομένων μόνο για το test."""
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            action TEXT,
            speed_kmh REAL
        )
    """)
    conn.commit()
    yield cursor 
    conn.close()

def test_insert_log_writes_to_database(mock_db_cursor: sqlite3.Cursor) -> None:
    """Ελέγχει τη λειτουργία εγγραφής στην in-memory βάση με Parameterized Query (?, ?, ?)."""
    test_user = "admin_hev"
    test_action = "engine_start"
    test_speed = 0.0

    mock_db_cursor.execute(
        "INSERT INTO logs (user, action, speed_kmh) VALUES (?, ?, ?)",
        (test_user, test_action, test_speed)
    )
    
    mock_db_cursor.execute("SELECT * FROM logs WHERE user=?", (test_user,))
    row = mock_db_cursor.fetchone()
    
    assert row is not None, "Το log δεν αποθηκεύτηκε στη βάση!"
    assert row[IDX_USER] == "admin_hev", "Αποθηκεύτηκε λάθος όνομα χρήστη"
    assert row[IDX_ACTION] == "engine_start", "Αποθηκεύτηκε λάθος action"