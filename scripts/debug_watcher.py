import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Checking imports...")
try:
    import cloudinary
    print("OK: cloudinary imported")
except ImportError as e:
    print(f"FAIL: cloudinary failed: {e}")

try:
    from app.database import get_db_context
    print("OK: get_db_context imported")
except ImportError as e:
    print(f"FAIL: app.database failed: {e}")

try:
    from watchdog.observers import Observer
    print("OK: watchdog imported")
except ImportError as e:
    print(f"FAIL: watchdog failed: {e}")

print("Done check.")
