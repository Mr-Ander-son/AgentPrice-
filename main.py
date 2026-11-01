

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
    
   