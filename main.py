
def check_product(product_name):
    return {
        "product": product_name,
        "available": True,
        "price": 29.99,
        "currency": "USD",
        "status": "demo_data"
    }

print(check_product("Running Shoes"))
