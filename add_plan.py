from src.database import plans_col

def add_dummy_plans():
    # Clear existing to prevent duplicate ID errors while testing
    plans_col.delete_many({})
    
    plans = [
        {"_id": 1, "name": "Basic Profile VIP", "price": 10.0, "duration_days": 30},
        {"_id": 2, "name": "Premium Signals Gold", "price": 49.0, "duration_days": 90},
        {"_id": 3, "name": "Lifetime Whale Access", "price": 199.0, "duration_days": 3650},
    ]
    
    plans_col.insert_many(plans)
    print("Successfully added 3 dummy VIP plans to your MongoDB Cluster!")

if __name__ == "__main__":
    add_dummy_plans()
