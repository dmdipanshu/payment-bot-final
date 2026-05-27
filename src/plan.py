import src.database as db

def add_dummy_plans():
<<<<<<< HEAD
    """
    Upsert default plans into the database.
    Uses replace_one with upsert to avoid wiping existing plans
    and breaking active subscription references.
    """
    if db.plans_col is None:
        print("Error: Database not initialized yet.")
        return
=======
    # Clear existing to prevent duplicate ID errors while testing
    if db.plans_col is None:
        print("Error: Database not initialized yet.")
        return
        
    db.plans_col.delete_many({})
>>>>>>> e8865ce1858bd4bcace14c672cea2f01ae7661d4
    
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
    
<<<<<<< HEAD
    for plan in plans:
        db.plans_col.replace_one({"_id": plan["_id"]}, plan, upsert=True)
    
    print("Successfully upserted 4 VIP plans (existing subscriptions preserved).")
=======
    db.plans_col.insert_many(plans)
    print("Successfully added 4 numbered VIP plans with INR ₹ currency!")
>>>>>>> e8865ce1858bd4bcace14c672cea2f01ae7661d4

if __name__ == "__main__":
    from src.database import init_db
    init_db()
    add_dummy_plans()
