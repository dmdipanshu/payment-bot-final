"""
Razorpay Client Wrapper
-----------------------
Handles Razorpay SDK initialization and QR Code generation.
Each QR code is unique per user + plan, single-use, and auto-closes after payment.
"""

import os
import time
import razorpay

# Lazy-initialized client
_client = None


def get_razorpay_client():
    """Get or initialize the Razorpay client singleton."""
    global _client
    if _client is None:
        key_id = os.getenv("RAZORPAY_KEY_ID", "")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        if not key_id or not key_secret:
            raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in .env")
        _client = razorpay.Client(auth=(key_id, key_secret))
    return _client


def create_qr_code(amount_inr, name, description, notes=None, close_after_minutes=30):
    """
    Create a single-use UPI QR code via Razorpay API.
    
    Args:
        amount_inr: Amount in INR (e.g., 99 for ₹99)
        name: Label for the QR code (shown in dashboard)
        description: Description of the payment
        notes: Dict of metadata to attach (e.g., telegram_id, plan_id)
        close_after_minutes: Auto-close QR after this many minutes (default 30)
    
    Returns:
        dict with keys: qr_id, image_url, amount, close_by
    """
    client = get_razorpay_client()
    
    # Razorpay expects amount in paise (1 INR = 100 paise)
    amount_paise = int(amount_inr * 100)
    
    # Calculate close_by timestamp (Unix epoch)
    close_by = int(time.time()) + (close_after_minutes * 60)
    
    qr_data = {
        "type": "upi_qr",
        "name": name,
        "usage": "single_use",
        "fixed_amount": True,
        "payment_amount": amount_paise,
        "description": description,
        "close_by": close_by,
    }
    
    if notes:
        qr_data["notes"] = notes
    
    response = client.qrcode.create(qr_data)
    
    return {
        "qr_id": response["id"],
        "image_url": response.get("image_url", ""),
        "amount": amount_inr,
        "close_by": close_by,
    }


def fetch_qr_code(qr_id):
    """Fetch QR code details including payment status."""
    client = get_razorpay_client()
    return client.qrcode.fetch(qr_id)


def close_qr_code(qr_id):
    """Manually close/expire a QR code."""
    client = get_razorpay_client()
    try:
        return client.qrcode.close(qr_id)
    except Exception as e:
        print(f"Error closing QR {qr_id}: {e}")
        return None


def verify_webhook_signature(body, signature, webhook_secret):
    """
    Verify Razorpay webhook signature for security.
    
    Args:
        body: Raw request body (string)
        signature: x-razorpay-signature header value
        webhook_secret: Webhook secret from Razorpay Dashboard
    
    Returns:
        True if signature is valid
    
    Raises:
        razorpay.errors.SignatureVerificationError if invalid
    """
    client = get_razorpay_client()
    client.utility.verify_webhook_signature(body, signature, webhook_secret)
    return True
