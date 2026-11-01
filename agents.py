import hashlib
import secrets
import sqlite3
import sys

from database import DB_PATH, init_database


def register_agent(name: str):
    init_database()

    api_key = "ap_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "INSERT INTO agents (name, api_key_hash) VALUES (?, ?)",
            (name, key_hash)
        )
        agent_id = cursor.lastrowid

    print(f"Agent registered! ID: {agent_id}")
    print(f"Name: {name}")
    print(f"API key: {api_key}")
    print("Save this key securely. It will not be shown again.")


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print('Usage: python agents.py "Test Agent"')
        sys.exit(1)

    register_agent(sys.argv[1].strip())