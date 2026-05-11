"""
Legacy plan seeder — redirects to src/plan.py
Run 'python -m src.plan' instead.
"""
from src.database import init_db
from src.plan import add_dummy_plans

if __name__ == "__main__":
    init_db()
    add_dummy_plans()
