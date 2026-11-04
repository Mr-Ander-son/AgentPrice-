
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb
from dotenv import dotenv_values
from database import DB_PATH

url = dotenv_values(".env").get("DATABASE_URL")

if not url:
    raise SystemExit("ERROR: Neon DATABASE_URL missing")

if not DB_PATH.is_file():
    raise SystemExit("ERROR: SQLite database not found")


def utc_date(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# Create a fresh snapshot before migrating.
backup_dir = Path("backups")
backup_dir.mkdir(exist_ok=True)

stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
snapshot = backup_dir / f"pre-neon-{stamp}.db"

with closing(sqlite3.connect(DB_PATH)) as source:
    with closing(sqlite3.connect(snapshot)) as target:
        source.backup(target)

print("SQLite snapshot created:", snapshot)

tables = (
    "agents",
    "usage_events",
    "demo_billing_ledger"
)

with closing(sqlite3.connect(snapshot)) as local:
    local.row_factory = sqlite3.Row

    if local.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise SystemExit("ERROR: SQLite integrity check failed")

    if local.execute("PRAGMA foreign_key_check").fetchall():
        raise SystemExit("ERROR: SQLite foreign key check failed")

    records = {
        table: local.execute(f"SELECT * FROM {table}").fetchall()
        for table in tables
    }

print("SQLite records:", [len(records[t]) for t in tables])

if tuple(len(records[t]) for t in tables) != (2, 9, 9):
    raise SystemExit("STOP: SQLite counts changed. Review before migration.")

# Neon changes are committed only if everything succeeds.
with psycopg.connect(url, connect_timeout=15) as cloud:
    with cloud.cursor() as cur:

        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            if cur.fetchone()[0] != 0:
                raise RuntimeError(
                    f"STOP: Neon table {table} is not empty"
                )

        for row in records["agents"]:
            cur.execute(
                """
                INSERT INTO agents
                    (id, name, api_key_hash, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    row["id"],
                    row["name"],
                    row["api_key_hash"],
                    utc_date(row["created_at"])
                )
            )

        for row in records["usage_events"]:
            response = (
                Jsonb(json.loads(row["response_json"]))
                if row["response_json"] is not None else None
            )

            cur.execute(
                """
                INSERT INTO usage_events
                    (id, agent_id, endpoint, billable,
                     request_id, barcode, response_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["id"],
                    row["agent_id"],
                    row["endpoint"],
                    bool(row["billable"]),
                    row["request_id"],
                    row["barcode"],
                    response,
                    utc_date(row["created_at"])
                )
            )

        for row in records["demo_billing_ledger"]:
            cur.execute(
                """
                INSERT INTO demo_billing_ledger
                    (usage_event_id, agent_id, amount_micro_usd,
                     status, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    row["usage_event_id"],
                    row["agent_id"],
                    row["amount_micro_usd"],
                    row["status"],
                    utc_date(row["created_at"])
                )
            )

        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            expected = len(records[table])

            print(f"{table}: {count}/{expected} transferred")

            if count != expected:
                raise RuntimeError("Migration verification failed")

        for table in ("agents", "usage_events"):
            highest_id = max(row["id"] for row in records[table])
            cur.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence(%s, 'id'),
                    %s,
                    true
                )
                """,
                (table, highest_id)
            )

print("PASS: All AgentPrice records migrated to Neon!")
print("SQLite original and backup preserved.")
