
from fastapi import FastAPI, Header, HTTPException

from neon_store import (
    authenticate_agent_neon,
    get_agent_usage_neon,
    get_agent_billing_neon,
    get_agent_history_neon
)

app = FastAPI(
    title="AgentPrice Neon Preview",
    description="Cloud database API testing",
    version="0.1.0"
)


def require_agent(api_key: str | None):
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )

    agent = authenticate_agent_neon(api_key)

    if agent is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return agent


@app.get("/")
def home():
    return {
        "service": "AgentPrice",
        "database": "Neon PostgreSQL",
        "status": "preview",
        "payments_enabled": False
    }


@app.get("/usage")
def get_usage(
    x_agent_key: str | None = Header(
        default=None,
        alias="X-Agent-Key"
    )
):
    agent = require_agent(x_agent_key)
    usage = get_agent_usage_neon(agent["agent_id"])

    return {
        **usage,
        "agent_name": agent["name"],
        "price_per_check_usd": "0.001"
    }


@app.get("/billing")
def get_billing(
    x_agent_key: str | None = Header(
        default=None,
        alias="X-Agent-Key"
    )
):
    agent = require_agent(x_agent_key)
    return get_agent_billing_neon(agent["agent_id"])


@app.get("/billing/history")
def billing_history(
    x_agent_key: str | None = Header(
        default=None,
        alias="X-Agent-Key"
    )
):
    agent = require_agent(x_agent_key)
    return get_agent_history_neon(agent["agent_id"])

import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from neon_store import (
    get_saved_response_neon,
    record_demo_check_once_neon
)


@app.get("/check")
def check_product_neon(
    barcode: str,
    x_agent_key: str | None = Header(
        default=None,
        alias="X-Agent-Key"
    ),
    x_request_id: str | None = Header(
        default=None,
        alias="X-Request-ID"
    )
):
    # 1. Authenticate the AI agent
    agent = require_agent(x_agent_key)
    agent_id = agent["agent_id"]

    # 2. Validate the barcode
    if (
        not barcode.isascii()
        or not barcode.isdigit()
        or len(barcode) not in (8, 12, 13, 14)
    ):
        raise HTTPException(
            status_code=422,
            detail="Invalid product barcode"
        )

    # 3. Require a unique request ID
    if (
        not x_request_id
        or not x_request_id.strip()
        or len(x_request_id) > 128
    ):
        raise HTTPException(
            status_code=400,
            detail="X-Request-ID header required (1-128 characters)"
        )

    # 4. Check Neon for a previous response
    try:
        saved = get_saved_response_neon(
            agent_id,
            barcode,
            x_request_id
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )

    if saved is not None:
        return saved

    # 5. Look up the product using Open Food Facts
    url = (
        "https://world.openfoodfacts.org"
        f"/api/v2/product/{barcode}.json"
        "?fields=code,product_name,brands"
    )

    request = Request(
        url,
        headers={
            "User-Agent": "AgentPrice-Preview/0.1"
        }
    )

    try:
        with urlopen(request, timeout=15) as response:
            product_data = json.load(response)

    except HTTPError as error:
        if error.code == 404:
            return {
                "barcode": barcode,
                "found": False,
                "message": "Product not found"
            }

        raise HTTPException(
            status_code=502,
            detail="Product lookup service error"
        )

    except (URLError, TimeoutError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Product lookup unavailable"
        )

    # 6. Never bill for a missing product
    if product_data.get("status") != 1:
        return {
            "barcode": barcode,
            "found": False,
            "message": "Product not found"
        }

    product = product_data.get("product") or {}

    result = {
        "barcode": barcode,
        "found": True,
        "name": product.get("product_name"),
        "brand": product.get("brands"),
        "price": None,
        "available": None,
        "price_verified": False,
        "availability_verified": False,
        "source": "Open Food Facts"
    }

    # 7. Record the check and simulated billing atomically
    try:
        created = record_demo_check_once_neon(
            agent_id,
            barcode,
            x_request_id,
            result
        )

        if not created:
            # Another simultaneous request already recorded it
            return get_saved_response_neon(
                agent_id,
                barcode,
                x_request_id
            )

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )

    return result



@app.get("/pricing")
def get_pricing_neon():
    return {
        "service": "AgentPrice",
        "price_per_check_usd": "0.001",
        "billing_status": "demo_only",
        "payment_required": False
    }
