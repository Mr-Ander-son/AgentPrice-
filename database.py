
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("agentprice.db")


def init_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_key_hash TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                billable INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)


if __name__ == "__main__":
    init_database()
    print("AgentPrice database initialized!")

    
def record_usage(agent_id: int, endpoint: str, billable: bool = False):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO usage_events (agent_id, endpoint, billable)
            VALUES (?, ?, ?)
            """,
            (agent_id, endpoint, int(billable))
        )

