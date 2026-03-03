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
    add_dummy_plans()
