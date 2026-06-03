"""
Payment Receipt Generator
--------------------------
Generates a premium-styled payment receipt image using PIL.
Sent to the user after successful payment verification.
"""

from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw
from src.vip_card import _load_font


# Pre-load fonts for receipt
_FONT_TITLE = _load_font(48, bold=True)
_FONT_HEADING = _load_font(32, bold=True)
_FONT_LABEL = _load_font(26, bold=True)
_FONT_VALUE = _load_font(26, bold=False)
_FONT_SMALL = _load_font(20, bold=False)
_FONT_STAMP = _load_font(44, bold=True)

# Colors
BG_COLOR = (18, 18, 32)
GOLD = (212, 175, 55)
WHITE = (255, 255, 255)
LIGHT_GRAY = (180, 180, 200)
DARK_LINE = (40, 40, 60)
GREEN = (46, 204, 113)
ACCENT_BLUE = (88, 130, 255)


def generate_receipt_image(
    username, telegram_id, plan_name, amount, qr_id,
    payment_id=None, expiry_date=None
):
    """
    Generate a premium payment receipt image.

    Args:
        username: Telegram username
        telegram_id: User's Telegram ID
        plan_name: Name of the purchased plan
        amount: Amount paid in INR
        qr_id: Razorpay QR code ID
        payment_id: Razorpay payment ID (optional)
        expiry_date: Subscription expiry datetime (optional)

    Returns:
        BytesIO containing the receipt PNG image, or None on failure
    """
    try:
        W, H = 800, 900
        img = Image.new("RGB", (W, H), BG_COLOR)
        draw = ImageDraw.Draw(img)

        # ---- Top gold accent bar ----
        draw.rectangle([0, 0, W, 8], fill=GOLD)

        # ---- Header ----
        y = 35
        draw.text((W // 2, y), "PAYMENT RECEIPT", font=_FONT_TITLE, fill=GOLD, anchor="mt")
        y += 65

        # Subtitle
        now_str = datetime.utcnow().strftime("%B %d, %Y • %H:%M UTC")
        draw.text((W // 2, y), now_str, font=_FONT_SMALL, fill=LIGHT_GRAY, anchor="mt")
        y += 45

        # ---- Divider ----
        draw.line([(50, y), (W - 50, y)], fill=GOLD, width=2)
        y += 30

        # ---- Receipt Details ----
        def draw_row(label, value, y_pos, value_color=WHITE):
            draw.text((60, y_pos), label, font=_FONT_LABEL, fill=LIGHT_GRAY)
            draw.text((W - 60, y_pos), str(value), font=_FONT_VALUE, fill=value_color, anchor="rt")
            return y_pos + 55

        y = draw_row("Customer", f"@{username}", y)
        y = draw_row("Telegram ID", str(telegram_id), y)

        # Light divider
        draw.line([(60, y - 10), (W - 60, y - 10)], fill=DARK_LINE, width=1)

        y = draw_row("Plan", plan_name, y, GOLD)
        y = draw_row("Amount Paid", f"Rs.{amount}", y, GREEN)

        if expiry_date:
            if isinstance(expiry_date, datetime):
                exp_str = expiry_date.strftime("%Y-%m-%d %H:%M UTC")
            else:
                exp_str = str(expiry_date)
            y = draw_row("Valid Until", exp_str, y, ACCENT_BLUE)

        # Light divider
        draw.line([(60, y - 10), (W - 60, y - 10)], fill=DARK_LINE, width=1)

        y = draw_row("QR ID", qr_id, y)
        if payment_id:
            y = draw_row("Payment ID", payment_id, y)

        txn_ref = f"TXN-{telegram_id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        y = draw_row("Reference", txn_ref, y)

        # ---- Divider ----
        y += 10
        draw.line([(50, y), (W - 50, y)], fill=GOLD, width=2)
        y += 30

        # ---- VERIFIED Stamp ----
        stamp_w, stamp_h = 280, 70
        stamp_x = (W - stamp_w) // 2
        stamp_y = y
        try:
            draw.rounded_rectangle(
                [stamp_x, stamp_y, stamp_x + stamp_w, stamp_y + stamp_h],
                fill=(30, 80, 50), outline=GREEN, width=3, radius=15
            )
        except (AttributeError, TypeError):
            draw.rectangle(
                [stamp_x, stamp_y, stamp_x + stamp_w, stamp_y + stamp_h],
                fill=(30, 80, 50), outline=GREEN, width=3
            )
        draw.text(
            (W // 2, stamp_y + stamp_h // 2),
            "VERIFIED", font=_FONT_STAMP, fill=GREEN, anchor="mm"
        )
        y = stamp_y + stamp_h + 30

        # ---- Footer ----
        draw.text(
            (W // 2, y),
            "Auto-verified via Razorpay UPI",
            font=_FONT_SMALL, fill=LIGHT_GRAY, anchor="mt"
        )
        y += 30
        draw.text(
            (W // 2, y),
            "This is a digitally generated receipt.",
            font=_FONT_SMALL, fill=(120, 120, 140), anchor="mt"
        )

        # ---- Bottom gold accent bar ----
        draw.rectangle([0, H - 8, W, H], fill=GOLD)

        # Save
        buf = BytesIO()
        buf.name = "payment_receipt.png"
        img.save(buf, "PNG", quality=95)
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"Error generating receipt: {e}")
        return None
