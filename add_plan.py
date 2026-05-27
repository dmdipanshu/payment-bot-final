<<<<<<< HEAD
"""
Legacy plan seeder — redirects to src/plan.py
Run 'python -m src.plan' instead.
"""
from src.database import init_db
from src.plan import add_dummy_plans

if __name__ == "__main__":
    init_db()
=======
from src.database import plans_col

def add_dummy_plans():
    # Clear existing to prevent duplicate ID errors while testing
    plans_col.delete_many({})
    
    plans = [
        {
            "_id": 1,
            "name": "1st Plan - 1 Month",
            "price": 99,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 30
        },
        {
            "_id": 2,
            "name": "2nd Plan - 6 Months",
            "price": 149,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 180
        },
        {
            "_id": 3,
            "name": "3rd Plan - 1 Year",
            "price": 199,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 365
        },
        {
            "_id": 4,
            "name": "4th Plan - Lifetime",
            "price": 299,
            "currency": "INR",
            "currency_symbol": "₹",
            "duration_days": 3650  # 10 years
        },
    ]
    
    plans_col.insert_many(plans)
    print("Successfully added 4 numbered VIP plans with INR ₹ currency!")

if __name__ == "__main__":
>>>>>>> e8865ce1858bd4bcace14c672cea2f01ae7661d4
    add_dummy_plans()
