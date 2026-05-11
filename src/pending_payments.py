"""
Pending Payments Tracker
------------------------
Manages the mapping between Razorpay QR codes and Telegram users.
When a QR is generated, we store the mapping. When Razorpay confirms payment
via webhook, we look up this mapping to know which user paid for which plan.
"""

from datetime import datetime
import src.database as db


def _get_collection():
    """Get the pending_payments MongoDB collection."""
    if db.db is None:
        raise RuntimeError("Database not initialized")
    return db.db["pending_payments"]


def create_pending_payment(telegram_id, username, plan_id, plan_name, amount, qr_id):
    """
    Store a pending payment record when a QR code is generated for a user.
    
    Args:
        telegram_id: User's Telegram ID
        username: User's Telegram username
        plan_id: ID of the plan being purchased
        plan_name: Name of the plan
        amount: Amount in INR
        qr_id: Razorpay QR Code ID
    
    Returns:
        The inserted document
    """
    col = _get_collection()
    
    doc = {
        "telegram_id": telegram_id,
        "username": username,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "amount": amount,
        "qr_id": qr_id,
        "status": "pending",        # pending | paid | expired | cancelled
        "created_at": datetime.utcnow(),
        "paid_at": None,
        "razorpay_payment_id": None,
    }
    
    col.insert_one(doc)
    return doc


def find_pending_by_qr_id(qr_id):
    """
    Look up a pending payment by Razorpay QR code ID.
    Returns the document or None.
    """
    col = _get_collection()
    return col.find_one({"qr_id": qr_id, "status": "pending"})


def mark_payment_paid(qr_id, razorpay_payment_id=None):
    """
    Mark a pending payment as paid after webhook confirmation.
    
    Args:
        qr_id: Razorpay QR Code ID
        razorpay_payment_id: The Razorpay payment ID from the webhook
    
    Returns:
        The updated document, or None if not found
    """
    col = _get_collection()
    result = col.find_one_and_update(
        {"qr_id": qr_id, "status": "pending"},
        {"$set": {
            "status": "paid",
            "paid_at": datetime.utcnow(),
            "razorpay_payment_id": razorpay_payment_id,
        }},
        return_document=True
    )
    return result


def mark_payment_expired(qr_id):
    """Mark a pending payment as expired (QR code timed out)."""
    col = _get_collection()
    col.update_one(
        {"qr_id": qr_id, "status": "pending"},
        {"$set": {"status": "expired"}}
    )


def get_pending_payments_for_user(telegram_id):
    """Get all pending payments for a specific user."""
    col = _get_collection()
    return list(col.find({"telegram_id": telegram_id, "status": "pending"}))


def is_event_already_processed(qr_id):
    """
    Check if this QR code payment was already processed (idempotency check).
    Prevents duplicate processing if Razorpay sends the webhook more than once.
    """
    col = _get_collection()
    doc = col.find_one({"qr_id": qr_id})
    if doc and doc["status"] == "paid":
        return True
    return False
