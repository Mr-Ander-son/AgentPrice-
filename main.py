

from fastapi import FastAPI

app = FastAPI(title="AgentPrice")


from fastapi import Header, HTTPException
from agents import authenticate_agent
from database import record_usage

@app.get("/")

def home():

    return {"message": "AgentPrice API is running"}



@app.get("/check")
def check_product(
    barcode: str,
    x_agent_key: str | None = Header(default=None, alias="X-Agent-Key")
):
    if not x_agent_key:
        raise HTTPException(status_code=401, detail="API key required")

    agent = authenticate_agent(x_agent_key)
    if agent is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    result = lookup_product(barcode)

    record_usage(agent["agent_id"], "/check", billable=False)
    return {
        **result,
        "agent_id": agent["agent_id"],
        "price": None,
        "available": None,
        "price_verified": False,
        "availability_verified": False
    }



@app.get("/pricing")
def pricing():
    return {
        "service": "AgentPrice",
        "price_per_check_usd": "0.001",
        "billing_status": "demo_only",
        "payment_required": False
    }

    
@app.get("/lookup")
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
def get_usage():
    with usage_lock:
        total = usage_stats["successful_checks"]

    return {
        "successful_checks": total,
        "price_per_check_usd": "0.001",
        "billing_status": "demo_only"
    }


    
   