

from fastapi import FastAPI

app = FastAPI(title="AgentPrice")


from fastapi import Header, HTTPException
from agents import authenticate_agent
from database import record_usage, DB_PATH
from billing import (
    get_billing_summary,
    record_demo_check_once,
    get_saved_response
)
import sqlite3

@app.get("/")

def home():

    return {"message": "AgentPrice API is running"}



@app.get("/check")

def check_product(
    barcode: str,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID")
):

    if not x_agent_key:
        raise HTTPException(status_code=401, detail="API key required")

    agent = authenticate_agent(x_agent_key)
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")


    if not x_request_id or not x_request_id.strip() or len(x_request_id) > 128:
        raise HTTPException(
            status_code=400,
            detail="X-Request-ID must contain 1 to 128 characters"
        )

 
    try:
        saved = get_saved_response(
            agent["agent_id"], barcode, x_request_id
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if saved is not None:
        return saved

    result = lookup_product(barcode)

    if not result.get("found"):
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    response_data = {
        **result,
        "agent_id": agent["agent_id"],
        "price": None,
        "available": None,
        "price_verified": False,
        "availability_verified": False
    }

    try:
        new_request = record_demo_check_once(
            agent["agent_id"],
            barcode,
            x_request_id,
            response_data
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if not new_request:
        saved = get_saved_response(
            agent["agent_id"], barcode, x_request_id
        )
        if saved is not None:
            return saved

    return response_data

    
@app.get("/pricing")
def pricing():
    return {
        "service": "AgentPrice",
        "price_per_check_usd": "0.001",
        "billing_status": "demo_only",
        "payment_required": False
    }

    

def lookup_product(barcode: str):
    import json
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from fastapi import HTTPException

    if not barcode.isdigit() or not 8 <= len(barcode) <= 14:
        raise HTTPException(
            status_code=400,
            detail="Enter a barcode with 8 to 14 digits"
        )

    api_url = (
        f"https://world.openfoodfacts.org/api/v3/product/{barcode}.json"
        "?fields=code,product_name,brands,quantity"
    )

    request = Request(
        api_url,
        headers={
            "User-Agent": "AgentPrice/0.1 (https://github.com/Mr-Ander-son/AgentPrice-)"
        }
    )

    try:
        with urlopen(request, timeout=10) as response:
            data = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return {"barcode": barcode, "found": False}
        raise HTTPException(
            status_code=502,
            detail="Product provider returned an error"
        )
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="Product provider is unavailable"
        )

    product = data.get("product") or {}

    if not product:
        return {"barcode": barcode, "found": False}

    return {
        "barcode": barcode,
        "found": True,
        "name": product.get("product_name"),
        "brand": product.get("brands"),
        "quantity": product.get("quantity"),
        "source": f"https://world.openfoodfacts.org/product/{barcode}",
        "status": "community_database_record"
    }

    
from threading import Lock

usage_lock = Lock()
usage_stats = {"successful_checks": 0}


@app.middleware("http")
async def track_usage(request, call_next):
    response = await call_next(request)

    if request.url.path == "/check" and response.status_code == 200:
        with usage_lock:
            usage_stats["successful_checks"] += 1

    return response



@app.get("/usage")
def get_usage(
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")
):
    if not x_agent_key:
        raise HTTPException(status_code=401, detail="API key required")

    agent = authenticate_agent(x_agent_key)
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM usage_events WHERE agent_id = ? AND endpoint = ?",
            (agent["agent_id"], "/check")
        ).fetchone()[0]

    return {
        "agent_id": agent["agent_id"],
        "agent_name": agent["name"],
        "total_checks": total,
        "price_per_check_usd": "0.001",
        "billing_status": "demo_only"
    }

  
@app.get("/billing")
def get_billing(
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")
):
    if not x_agent_key:
        raise HTTPException(status_code=401, detail="API key required")

    agent = authenticate_agent(x_agent_key)
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return get_billing_summary(agent["agent_id"])

    
@app.get("/billing/history")
def billing_history(
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")
):
    if not x_agent_key:
        raise HTTPException(status_code=401, detail="API key required")

    agent = authenticate_agent(x_agent_key)
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT u.request_id, u.barcode, u.created_at,
                   l.amount_micro_usd, l.status
            FROM demo_billing_ledger AS l
            JOIN usage_events AS u ON u.id = l.usage_event_id
            WHERE l.agent_id = ? AND u.agent_id = ?
            ORDER BY l.usage_event_id DESC
            LIMIT 20
            """,
            (agent["agent_id"], agent["agent_id"])
        ).fetchall()

    return {
        "agent_id": agent["agent_id"],
        "payments_enabled": False,
        "transactions": [
            {
                "request_id": row[0],
                "barcode": row[1],
                "date": row[2],
                "amount_micro_usd": row[3],
                "status": row[4]
            }
            for row in rows
        ]
    }

  



    
   