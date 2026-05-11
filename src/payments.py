"""
Payments Module
---------------
Generates Razorpay UPI QR codes for payment processing.
Each QR is single-use, tied to a specific user and plan,
and auto-expires after 30 minutes.
"""

from src.razorpay_client import create_qr_code
from src.pending_payments import create_pending_payment


def generate_razorpay_qr(telegram_id, username, plan_id, plan_name, amount):
    """
    Generate a unique Razorpay UPI QR code for a user's plan purchase.
    
    Args:
        telegram_id: User's Telegram ID
        username: User's Telegram username
        plan_id: Plan ID being purchased
        plan_name: Plan name for display
        amount: Amount in INR
    
    Returns:
        dict with: qr_id, image_url, amount
        or None on failure
    """
    try:
        # Create QR code via Razorpay with user metadata in notes
        qr_result = create_qr_code(
            amount_inr=amount,
            name=f"VIP_{telegram_id}_{plan_id}",
            description=f"VIP Plan: {plan_name} for User {telegram_id}",
            notes={
                "telegram_id": str(telegram_id),
                "plan_id": str(plan_id),
                "plan_name": plan_name,
                "username": username,
            },
            close_after_minutes=30,
        )
        
        # Store pending payment mapping in database
        create_pending_payment(
            telegram_id=telegram_id,
            username=username,
            plan_id=plan_id,
            plan_name=plan_name,
            amount=amount,
            qr_id=qr_result["qr_id"],
        )
        
        return qr_result
        
    except Exception as e:
        print(f"Error generating Razorpay QR for user {telegram_id}: {e}")
        return None
