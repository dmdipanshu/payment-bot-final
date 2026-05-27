"""
Payments Module
---------------
Generates Razorpay UPI QR codes for payment processing.
Each QR is single-use, tied to a specific user and plan,
and auto-expires after 30 minutes.
"""

import cv2
import numpy as np
import requests
from src.razorpay_client import create_qr_code
from src.pending_payments import create_pending_payment


def decode_qr_from_url(url):
    """
    Download QR image and decode the UPI string from it.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            image_bytes = np.frombuffer(resp.content, dtype=np.uint8)
            image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
            if image is not None:
                detector = cv2.QRCodeDetector()
                data, bbox, straight_qrcode = detector.detectAndDecode(image)
                if data:
                    return data
    except Exception as e:
        print(f"Error decoding QR image from {url}: {e}")
    return None


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
        dict with: qr_id, image_url, amount, upi_url
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
        
        # Decode the UPI url from the QR code image URL
        image_url = qr_result.get("image_url", "")
        upi_url = None
        if image_url:
            upi_url = decode_qr_from_url(image_url)
            print(f"Decoded UPI URL for QR {qr_result['qr_id']}: {upi_url}")
            qr_result["upi_url"] = upi_url
        
        # Store pending payment mapping in database
        create_pending_payment(
            telegram_id=telegram_id,
            username=username,
            plan_id=plan_id,
            plan_name=plan_name,
            amount=amount,
            qr_id=qr_result["qr_id"],
            upi_url=upi_url,
            image_url=image_url,
        )
        
        return qr_result
        
    except Exception as e:
        print(f"Error generating Razorpay QR for user {telegram_id}: {e}")
        return None
