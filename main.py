

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