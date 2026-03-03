import os
import sys
import sqlite3
import time


sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

try:
    from db_logger import log_telemetry, DB_PATH
except ImportError:
    print("❌ Error: Δεν βρέθηκε το 'db_logger.py'. Είσαι σίγουρα στον φάκελο 'thesis';")
    sys.exit(1)

print("🔍 --- DIAGNOSTIC TEST START ---")
print(f"📂 Database Path detected: {DB_PATH}")


if not os.path.exists(DB_PATH):
    print("❌ CRITICAL: Το αρχείο .db δεν υπάρχει! Τρέξε 'python manage.py init'")
    sys.exit(1)
else:
    print("✅ File check passed: Η βάση υπάρχει.")


print("\n✍️  Testing WRITE operation...")
try:

    test_speed = 999.9
    test_battery = 12.3
    log_telemetry(test_speed, test_battery, 50.0, source="TEST_SCRIPT")
    print("✅ Write executed without errors.")
except Exception as e:
    print(f"❌ Write Failed: {e}")
    sys.exit(1)


print("\n👓 Testing READ operation...")
try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    

    cursor.execute("SELECT * FROM telemetry WHERE log_source = 'TEST_SCRIPT' ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print(f"✅ SUCCESS! Retrieved data from DB:")
        print(f"   🆔 ID: {row[0]}")
        print(f"   🕒 Time: {row[1]}")
        print(f"   🚀 Speed: {row[2]} km/h (Πρέπει να είναι 999.9)")
        print(f"   🔋 Battery: {row[3]}%")
        print(f"   🏷️  Source: {row[5]}")
    else:
        print("❌ FAIL: Η εγγραφή έγινε αλλά δεν βρέθηκε! Κάτι πάει λάθος με το commit.")

    conn.close()

except Exception as e:
    print(f"❌ Read Failed: {e}")

print("\n🏁 --- DIAGNOSTIC TEST END ---")