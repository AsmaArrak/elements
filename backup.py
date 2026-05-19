"""
Run this BEFORE deploying to save your database.
Usage: python backup.py
"""
import subprocess
import base64
import os

print("Downloading database from Railway...")

cmd = 'railway run -- python -c "import os; print(os.getcwd()); import database; print(database.DB_PATH); print(os.path.exists(database.DB_PATH))"'
result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

print("Output:", result.stdout)
print("Errors:", result.stderr)
