
import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

from database import DB_PATH

env_file = Path(__file__).with_name(".env")

if env_file.exists():
    raise SystemExit(".env already exists. Do not overwrite it.")

api_key = "ap_" + secrets.token_urlsafe(32)
key_hash = hashlib.sha256(api_key.encode()).hexdigest()

with sqlite3.connect(DB_PATH) as conn:
    result = conn.execute(
        "UPDATE agents SET api_key_hash = ? WHERE id = ?",
        (key_hash, 1)
    )

    if result.rowcount != 1:
        raise SystemExit("Agent #1 not found")

    env_file.write_text(
        f"AGENTPRICE_TEST_API_KEY={api_key}\n"
    )
    os.chmod(env_file, 0o600)

print("Agent #1 has a new API key!")
print("Key saved privately in .env")
