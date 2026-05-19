"""
Run this AFTER deploying to restore your database.
Usage: python restore.py
"""
import subprocess
import base64
import os

backup_file = "elementals_backup.db"

if not os.path.exists(backup_file):
    print(f"ERROR: {backup_file} not found. Run backup.py first.")
    exit(1)

with open(backup_file, "rb") as f:
    data = f.read()

b64 = base64.b64encode(data).decode()
print(f"Restoring database ({len(data):,} bytes) to Railway...")

script = f"import base64; open('/app/elementals.db','wb').write(base64.b64decode('{b64}'))"

result = subprocess.run(
    f'railway run -- python -c "{script}"',
    capture_output=True, text=True, shell=True
)

if result.returncode == 0:
    print("Database restored successfully!")
else:
    print("ERROR during restore:")
    print(result.stderr)
