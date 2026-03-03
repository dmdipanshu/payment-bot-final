import os
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson.objectid import ObjectId

# Database setup — connection is deferred to init_db()
client = None
db = None
users_col = None
plans_col = None
subs_col = None

def init_db():
    """Initialize MongoDB connection. Returns True on success, False on failure."""
    global client, db, users_col, plans_col, subs_col
    mongo_uri = os.getenv("MONGO_URI", "")
    if not mongo_uri:
        print("ERROR: MONGO_URI environment variable is not set!")
        return False
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Force a connection attempt to verify it works
        client.admin.command('ping')
        db = client['payment_bot']
        users_col = db['users']
        plans_col = db['plans']
        subs_col = db['subscriptions']
        # Create indexes
        users_col.create_index("telegram_id", unique=True)
        subs_col.create_index([("user_telegram_id", 1), ("is_active", 1)])
        print("MongoDB Connected & Indexes Verified")
        return True
    except Exception as e:
        print(f"FATAL: MongoDB connection error: {e}")
        return False

def add_or_update_user(telegram_id, username, referrer_id=None):
    update_data = {"$set": {"username": username}}
    
    # We load the existing user to see if they already have fields
    existing = users_col.find_one({"telegram_id": telegram_id})
    
    if not existing:
        # If it's a completely new user
        update_data["$set"]["referral_count"] = 0
        if referrer_id:
            update_data["$set"]["referrer_id"] = referrer_id
            
    result = users_col.find_one_and_update(
        {"telegram_id": telegram_id},
        update_data,
        upsert=True,
        return_document=True
    )
    return result

def get_active_subscription(telegram_id):
    user = users_col.find_one({"telegram_id": telegram_id})
    if not user: return None
    
    sub = subs_col.find_one({
        "user_telegram_id": telegram_id,
        "is_active": True,
        "end_date": {"$gt": datetime.utcnow()}
    })
    
    if sub:
        plan = plans_col.find_one({"_id": sub["plan_id"]})
        if plan:
            return {"plan_name": plan["name"], "end_date": sub["end_date"]}
    return None

def create_subscription(telegram_id, plan_id):
    user = users_col.find_one({"telegram_id": telegram_id})
    plan = plans_col.find_one({"_id": int(plan_id)})
    
    if not user or not plan: return None
    
    subs_col.update_many(
        {"user_telegram_id": telegram_id, "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    end_date = datetime.utcnow() + timedelta(days=plan["duration_days"])
    new_sub = {
        "user_telegram_id": telegram_id,
        "plan_id": int(plan_id),
        "start_date": datetime.utcnow(),
        "end_date": end_date,
        "is_active": True
    }
    
    subs_col.insert_one(new_sub)
    return {"plan_name": plan["name"], "end_date": end_date, "referrer_id": user.get("referrer_id")}

def add_referral_bonus(referrer_telegram_id, bonus_days=7):
    referrer = users_col.find_one({"telegram_id": referrer_telegram_id})
    if not referrer: return False
    
    users_col.update_one({"telegram_id": referrer_telegram_id}, {"$inc": {"referral_count": 1}})
    
    active_sub = subs_col.find_one({
        "user_telegram_id": referrer_telegram_id,
        "is_active": True,
        "end_date": {"$gt": datetime.utcnow()}
    })
    
    if active_sub:
        new_end_date = active_sub["end_date"] + timedelta(days=bonus_days)
        subs_col.update_one({"_id": active_sub["_id"]}, {"$set": {"end_date": new_end_date}})
    else:
        fallback = plans_col.find_one()
        plan_id = fallback["_id"] if fallback else 1
        new_sub = {
            "user_telegram_id": referrer_telegram_id,
            "plan_id": plan_id,
            "start_date": datetime.utcnow(),
            "end_date": datetime.utcnow() + timedelta(days=bonus_days),
            "is_active": True
        }
        subs_col.insert_one(new_sub)
    return True

def get_expired_subscriptions():
    expired = subs_col.find({
        "is_active": True,
        "end_date": {"$lte": datetime.utcnow()}
    })
    return [{'sub_id': str(s["_id"]), 'telegram_id': s["user_telegram_id"]} for s in expired]

def get_expiring_soon_subscriptions(days=3):
    target_time = datetime.utcnow() + timedelta(days=days)
    start_window = target_time - timedelta(days=1)
    
    expiring = subs_col.find({
        "is_active": True,
        "end_date": {"$gt": start_window, "$lte": target_time}
    })
    return [{'sub_id': str(s["_id"]), 'telegram_id': s["user_telegram_id"], 'end_date': s["end_date"]} for s in expiring]

def deactivate_subscription(sub_id):
    try:
        subs_col.update_one({"_id": ObjectId(sub_id)}, {"$set": {"is_active": False}})
    except Exception as e:
        print(f"Error deactivating subscription {sub_id}: {e}")

def get_all_plans():
    plans = list(plans_col.find())
    return [{"id": p["_id"], "name": p["name"], "price": p["price"], "duration_days": p["duration_days"]} for p in plans]

def get_plan_by_id(plan_id):
    p = plans_col.find_one({"_id": int(plan_id)})
    if p:
        return {"id": p["_id"], "name": p["name"], "price": p["price"], "duration_days": p["duration_days"]}
    return None

def get_all_users():
    return [u["telegram_id"] for u in users_col.find({}, {"telegram_id": 1})]

def get_admin_stats():
    total_users = users_col.count_documents({})
    active_subs = subs_col.count_documents({
        "is_active": True,
        "end_date": {"$gt": datetime.utcnow()}
    })
    
    revenue = 0
    active_docs = subs_col.find({
        "is_active": True,
        "end_date": {"$gt": datetime.utcnow()}
    })
    
    for sub in active_docs:
        plan = plans_col.find_one({"_id": sub["plan_id"]})
        if plan:
            revenue += plan["price"]
            
    return {
        "total_users": total_users,
        "active_subs": active_subs,
        "current_revenue": revenue
    }

def get_full_analytics_data():
    users = list(users_col.find())
    export_data = []
    
    for u in users:
        sub = subs_col.find_one({"user_telegram_id": u["telegram_id"]}, sort=[("_id", -1)])
        plan_name = "None"
        status = "Inactive"
        end_date = "N/A"
        
        if sub:
            plan = plans_col.find_one({"_id": sub["plan_id"]})
            if plan: plan_name = plan["name"]
            end_date = sub["end_date"].strftime("%Y-%m-%d %H:%M:%S")
            if sub["is_active"] and sub["end_date"] > datetime.utcnow():
                status = "Active"
            else:
                status = "Expired"
                
        export_data.append({
            "telegram_id": u["telegram_id"],
            "username": u.get("username", "N/A"),
            "referrer_id": u.get("referrer_id", "None"),
            "referral_count": u.get("referral_count", 0),
            "plan_name": plan_name,
            "status": status,
            "end_date": end_date
        })
    return export_data
