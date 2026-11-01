import json
import sqlite3
from database import DB_PATH, init_database

PRICE_MICRO_USD = 1000  # $0.001


def initialize_billing():
    init_database()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS demo_billing_ledger (
                usage_event_id INTEGER PRIMARY KEY,
                agent_id INTEGER NOT NULL,
                amount_micro_usd INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'simulation',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usage_event_id) REFERENCES usage_events(id),
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)


def sync_demo_billing():
    initialize_billing()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR IGNORE INTO demo_billing_ledger
                (usage_event_id, agent_id, amount_micro_usd)
            SELECT id, agent_id, ?
            FROM usage_events
            WHERE endpoint = '/check'
        """, (PRICE_MICRO_USD,))

        for agent_id, checks, amount in conn.execute("""
            SELECT agent_id, COUNT(*), SUM(amount_micro_usd)
            FROM demo_billing_ledger
            GROUP BY agent_id
            ORDER BY agent_id
        """):
            print(
                f"Agent #{agent_id}: {checks} checks, "
                f"estimated cost ${amount / 1000000:.3f}"
            )


def get_billing_summary(agent_id: int):
    initialize_billing()

    with sqlite3.connect(DB_PATH) as conn:
        demo = conn.execute("""
            SELECT COUNT(*), COALESCE(SUM(amount_micro_usd), 0)
            FROM demo_billing_ledger
            WHERE agent_id = ? AND status = 'simulation'
        """, (agent_id,)).fetchone()

        billable = conn.execute("""
            SELECT COUNT(*)
            FROM usage_events
            WHERE agent_id = ? AND billable = 1
        """, (agent_id,)).fetchone()[0]

    return {
        "agent_id": agent_id,
        "simulated_checks": demo[0],
        "simulated_total_usd": f"{demo[1] / 1000000:.3f}",
        "billable_events": billable,
        "amount_due_usd": "0.000",
        "payments_enabled": False
    }

def record_demo_check(agent_id: int):
    initialize_billing()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        cursor = conn.execute(
            """
            INSERT INTO usage_events (agent_id, endpoint, billable)
            VALUES (?, ?, 0)
            """,
            (agent_id, "/check")
        )

        conn.execute(
            """
            INSERT INTO demo_billing_ledger
                (usage_event_id, agent_id, amount_micro_usd, status)
            VALUES (?, ?, ?, 'simulation')
            """,
            (cursor.lastrowid, agent_id, PRICE_MICRO_USD)
        )



def record_demo_check_once(
    agent_id: int,
    barcode: str,
    request_id: str,
    response_data: dict | None = None
):
    if not request_id or len(request_id) > 128:
        raise ValueError("Request ID must contain 1 to 128 characters")

    initialize_billing()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO usage_events
                (agent_id, endpoint, billable, request_id,
                 barcode, response_json)
            VALUES (?, '/check', 0, ?, ?, ?)
            """,
            (
                agent_id,
                request_id,
                barcode,
                json.dumps(response_data)
                if response_data is not None else None
            )
        )

        if cursor.rowcount == 0:
            existing = conn.execute(
                """
                SELECT barcode FROM usage_events
                WHERE agent_id = ? AND request_id = ?
                """,
                (agent_id, request_id)
            ).fetchone()

            if existing is None:
                raise RuntimeError("Could not record request")

            if existing[0] != barcode:
                raise ValueError("Request ID already used for another barcode")

            return False

        conn.execute(
            """
            INSERT INTO demo_billing_ledger
                (usage_event_id, agent_id, amount_micro_usd, status)
            VALUES (?, ?, ?, 'simulation')
            """,
            (cursor.lastrowid, agent_id, PRICE_MICRO_USD)
        )

    return True

def get_saved_response(agent_id: int, barcode: str, request_id: str):
    initialize_billing()

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT barcode, response_json
            FROM usage_events
            WHERE agent_id = ? AND request_id = ?
            """,
            (agent_id, request_id)
        ).fetchone()

    if row is None:
        return None

    if row[0] != barcode:
        raise ValueError(
            "Request ID already used for another barcode"
        )

    if row[1] is None:
        return None

    return json.loads(row[1])

if __name__ == "__main__":
    sync_demo_billing()
