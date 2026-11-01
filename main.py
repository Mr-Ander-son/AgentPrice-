

from fastapi import FastAPI

app = FastAPI(title="AgentPrice")

@app.get("/")

def home():

    return {"message": "AgentPrice API is running"}

@app.get("/check")

def check_product(product: str):

    return {

        "product": product,

        "available": True,

        "price": 29.99,

        "currency": "USD",

        "status": "demo_data"

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

    
   