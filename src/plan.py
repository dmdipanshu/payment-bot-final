import src.database as db

def add_dummy_plans():
    # Clear existing to prevent duplicate ID errors while testing
    if db.plans_col is None:
        print("Error: Database not initialized yet.")
        return
        
    db.plans_col.delete_many({})
    
    plans = [
        {
            "_id": 1,
            "name": "1 Month - ₹99",
            "price": 99,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 30
        },
        {
            "_id": 2,
            "name": "6 Months - ₹149",
            "price": 149,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 180
        },
        {
            "_id": 3,
            "name": "1 Year - ₹199",
            "price": 199,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 365
        },
        {
            "_id": 4,
            "name": "Lifetime - ₹299",
            "price": 299,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 3650  # 10 years
        },
    ]
    
    db.plans_col.insert_many(plans)
    print("Successfully added 4 numbered VIP plans with INR ₹ currency!")

if __name__ == "__main__":
    from src.database import init_db
    init_db()
    add_dummy_plans()
