
import hashlib
import psycopg
from dotenv import dotenv_values
from psycopg.types.json import Jsonb
from billing import PRICE_MICRO_USD


def get_neon_connection():
    url = dotenv_values(".env").get("DATABASE_URL")

    if not url:
        raise RuntimeError("Neon DATABASE_URL is missing")

    return psycopg.connect(url, connect_timeout=15)


def authenticate_agent_neon(api_key: str):
    if not api_key or not api_key.startswith("ap_"):
        return None

    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    with get_neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM agents WHERE api_key_hash = %s",
                (key_hash,)
            )
            agent = cur.fetchone()

    if agent is None:
        return None

    return {
        "agent_id": agent[0],
        "name": agent[1],
        "authenticated": True
    }


def get_agent_usage_neon(agent_id: int):
    with get_neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM usage_events
                WHERE agent_id = %s AND endpoint = '/check'
                """,
                (agent_id,)
            )
            total = cur.fetchone()[0]

    return {
        "agent_id": agent_id,
        "total_checks": total,
        "billing_status": "demo_only"
    }


def get_saved_response_neon(agent_id: int, barcode: str, request_id: str):
    with get_neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT barcode, response_json
                FROM usage_events
                WHERE agent_id = %s AND request_id = %s
                """,
                (agent_id, request_id)
            )
            row = cur.fetchone()

    if row is None:
        return None

    if row[0] != barcode:
        raise ValueError(
            "Request ID already used for another barcode"
        )

    return row[1]



def get_agent_billing_neon(agent_id: int):
    with get_neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(amount_micro_usd), 0)
                FROM demo_billing_ledger
                WHERE agent_id = %s AND status = 'simulation'
                """,
                (agent_id,)
            )
            checks, total_micro = cur.fetchone()

            cur.execute(
                """
                SELECT COUNT(*)
                FROM usage_events
                WHERE agent_id = %s AND billable = TRUE
                """,
                (agent_id,)
            )
            billable = cur.fetchone()[0]

    return {
        "agent_id": agent_id,
        "simulated_checks": checks,
        "simulated_total_usd": f"{total_micro / 1000000:.3f}",
        "billable_events": billable,
        "amount_due_usd": "0.000",
        "payments_enabled": False
    }



def get_agent_history_neon(agent_id: int):
    with get_neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT l.usage_event_id,
                       u.request_id,
                       u.barcode,
                       u.created_at,
                       l.amount_micro_usd,
                       l.status
                FROM demo_billing_ledger AS l
                JOIN usage_events AS u
                    ON u.id = l.usage_event_id
                WHERE l.agent_id = %s
                  AND u.agent_id = %s
                ORDER BY l.usage_event_id DESC
                LIMIT 20
                """,
                (agent_id, agent_id)
            )
            rows = cur.fetchall()

    return {
        "agent_id": agent_id,
        "payments_enabled": False,
        "transactions": [
            {
                "usage_event_id": row[0],
                "request_id": row[1],
                "barcode": row[2],
                "date": row[3].isoformat(),
                "amount_micro_usd": row[4],
                "status": row[5]
            }
            for row in rows
        ]
    }

def record_demo_check_once_neon(
    agent_id: int,
    barcode: str,
    request_id: str,
    response_data: dict
):
    if not request_id or not request_id.strip() or len(request_id) > 128:
        raise ValueError("Request ID must contain 1 to 128 characters")

    if not isinstance(response_data, dict):
        raise ValueError("Response data must be a dictionary")

    with get_neon_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usage_events
                    (agent_id, endpoint, billable,
                     request_id, barcode, response_json)
                VALUES (%s, '/check', FALSE, %s, %s, %s)
                ON CONFLICT (agent_id, request_id)
                    WHERE request_id IS NOT NULL
                DO NOTHING
                RETURNING id
                """,
                (
                    agent_id,
                    request_id,
                    barcode,
                    Jsonb(response_data)
                )
            )

            inserted = cur.fetchone()

            if inserted is None:
                cur.execute(
                    """
                    SELECT barcode FROM usage_events
                    WHERE agent_id = %s AND request_id = %s
                    """,
                    (agent_id, request_id)
                )
                existing = cur.fetchone()

                if existing is None:
                    raise RuntimeError("Could not record request")

                if existing[0] != barcode:
                    raise ValueError(
                        "Request ID already used for another barcode"
                    )

                return False

            usage_event_id = inserted[0]

            cur.execute(
                """
                INSERT INTO demo_billing_ledger
                    (usage_event_id, agent_id,
                     amount_micro_usd, status)
                VALUES (%s, %s, %s, 'simulation')
                """,
                (usage_event_id, agent_id, PRICE_MICRO_USD)
            )

    return True
