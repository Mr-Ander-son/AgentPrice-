
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

if __name__ == "__main__":
    sync_demo_billing()
