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
        # Index for fast Razorpay webhook QR lookups
        pending_col = db['pending_payments']
        pending_col.create_index("qr_id", unique=True)
        pending_col.create_index([("telegram_id", 1), ("status", 1)])
        # Index for scheduled broadcasts
        broadcasts_col = db['scheduled_broadcasts']
        broadcasts_col.create_index([("status", 1), ("send_at", 1)])
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
        update_data["$set"]["created_at"] = datetime.utcnow()
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


# ============ PLAN CRUD (Admin In-Bot Management) ============ #

def create_plan(name, price, duration_days):
    """Create a new plan with auto-incremented ID."""
    last_plan = plans_col.find_one(sort=[("_id", -1)])
    new_id = (last_plan["_id"] + 1) if last_plan else 1
    plan = {
        "_id": new_id,
        "name": name,
        "price": price,
        "currency": "INR",
        "currency_symbol": "₹",
        "duration_days": duration_days
    }
    plans_col.insert_one(plan)
    return plan

def update_plan(plan_id, **kwargs):
    """Update a plan's fields (name, price, duration_days)."""
    update_fields = {}
    for key in ("name", "price", "duration_days"):
        if key in kwargs and kwargs[key] is not None:
            update_fields[key] = kwargs[key]
    if not update_fields:
        return None
    plans_col.update_one({"_id": int(plan_id)}, {"$set": update_fields})
    return plans_col.find_one({"_id": int(plan_id)})

def delete_plan(plan_id):
    """Delete a plan by ID. Returns True if deleted."""
    result = plans_col.delete_one({"_id": int(plan_id)})
    return result.deleted_count > 0


# ============ SCHEDULED BROADCASTS ============ #

def create_scheduled_broadcast(admin_id, message_text, send_at, media_type=None, media_file_id=None):
    """Schedule a broadcast for a future date/time."""
    col = db['scheduled_broadcasts']
    doc = {
        "admin_id": admin_id,
        "message_text": message_text,
        "media_type": media_type,       # 'photo', 'document', or None
        "media_file_id": media_file_id,
        "send_at": send_at,
        "status": "pending",            # pending | sent | cancelled
        "created_at": datetime.utcnow(),
    }
    col.insert_one(doc)
    return doc

def get_due_broadcasts():
    """Get all pending broadcasts whose send_at time has passed."""
    col = db['scheduled_broadcasts']
    return list(col.find({
        "status": "pending",
        "send_at": {"$lte": datetime.utcnow()}
    }))

def mark_broadcast_sent(broadcast_id):
    """Mark a scheduled broadcast as sent."""
    from bson.objectid import ObjectId
    col = db['scheduled_broadcasts']
    col.update_one({"_id": broadcast_id}, {"$set": {"status": "sent", "sent_at": datetime.utcnow()}})

def get_pending_broadcasts():
    """Get all future pending broadcasts (for admin listing)."""
    col = db['scheduled_broadcasts']
    return list(col.find({"status": "pending"}).sort("send_at", 1))

def cancel_scheduled_broadcast(broadcast_id):
    """Cancel a pending scheduled broadcast."""
    from bson.objectid import ObjectId
    col = db['scheduled_broadcasts']
    result = col.update_one(
        {"_id": broadcast_id, "status": "pending"},
        {"$set": {"status": "cancelled"}}
    )
    return result.modified_count > 0


# ============ DRIP CAMPAIGN ============ #

def get_users_for_drip(days_since_join):
    """
    Get users who joined exactly N days ago and do NOT have an active subscription.
    Used by the drip campaign scheduler.
    """
    target_date = datetime.utcnow() - timedelta(days=days_since_join)
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Find users who joined on that specific day
    users = list(users_col.find({
        "created_at": {"$gte": start_of_day, "$lte": end_of_day}
    }))

    # Filter out users who already have an active subscription
    free_users = []
    for u in users:
        active = subs_col.find_one({
            "user_telegram_id": u["telegram_id"],
            "is_active": True,
            "end_date": {"$gt": datetime.utcnow()}
        })
        if not active:
            free_users.append(u)

    return free_users


# ============ SUBSCRIPTION WITH REMAINING DAYS ============ #

def get_subscription_with_countdown(telegram_id):
    """
    Get the active subscription with remaining days and total days for progress bar.
    Returns dict with plan_name, end_date, start_date, total_days, remaining_days, progress_pct
    or None.
    """
    sub = subs_col.find_one({
        "user_telegram_id": telegram_id,
        "is_active": True,
        "end_date": {"$gt": datetime.utcnow()}
    })
    if not sub:
        return None

    plan = plans_col.find_one({"_id": sub["plan_id"]})
    if not plan:
        return None

    now = datetime.utcnow()
    total_days = (sub["end_date"] - sub["start_date"]).days or 1
    remaining = (sub["end_date"] - now).days
    elapsed = total_days - remaining
    progress_pct = min(100, max(0, int((elapsed / total_days) * 100)))

    return {
        "plan_name": plan["name"],
        "start_date": sub["start_date"],
        "end_date": sub["end_date"],
        "total_days": total_days,
        "remaining_days": max(0, remaining),
        "progress_pct": progress_pct,
    }
