"""
Revenue Chart Generator
------------------------
Generates a dark-themed revenue bar chart image using pure PIL.
No matplotlib dependency needed.
"""

from io import BytesIO
from datetime import datetime, timedelta
from PIL import Image, ImageDraw
from src.vip_card import _load_font
import src.database as db


# Pre-load fonts
_FONT_TITLE = _load_font(40, bold=True)
_FONT_LABEL = _load_font(22, bold=False)
_FONT_AXIS = _load_font(18, bold=False)
_FONT_VALUE = _load_font(16, bold=False)
_FONT_STAT = _load_font(28, bold=True)
_FONT_STAT_LABEL = _load_font(20, bold=False)

# Colors
BG = (18, 18, 32)
GOLD = (212, 175, 55)
WHITE = (255, 255, 255)
LIGHT_GRAY = (140, 140, 160)
GRID_COLOR = (35, 35, 55)
BAR_COLOR_TOP = (88, 130, 255)
BAR_COLOR_BOTTOM = (46, 204, 113)
ACCENT_GREEN = (46, 204, 113)


def get_revenue_data(days=30):
    """
    Query pending_payments for paid transactions in the last N days,
    grouped by date.
    
    Returns:
        list of dicts: [{"date": "Jun 01", "amount": 299, "count": 3}, ...]
    """
    if db.db is None:
        return []

    col = db.db["pending_payments"]
    start_date = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$match": {"status": "paid", "paid_at": {"$gte": start_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$paid_at"}},
            "total": {"$sum": "$amount"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]

    results = list(col.aggregate(pipeline))

    # Fill in missing dates with 0
    date_map = {r["_id"]: {"amount": r["total"], "count": r["count"]} for r in results}
    data = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        key = d.strftime("%Y-%m-%d")
        label = d.strftime("%b %d")
        info = date_map.get(key, {"amount": 0, "count": 0})
        data.append({"date": label, "amount": info["amount"], "count": info["count"]})

    return data


def generate_revenue_chart(days=30):
    """
    Generate a revenue bar chart image for the last N days.
    
    Returns:
        BytesIO containing the chart PNG, or None on failure
    """
    try:
        data = get_revenue_data(days)
        if not data:
            return None

        # Chart dimensions
        W, H = 1200, 700
        MARGIN_LEFT = 80
        MARGIN_RIGHT = 40
        MARGIN_TOP = 120
        MARGIN_BOTTOM = 100
        CHART_W = W - MARGIN_LEFT - MARGIN_RIGHT
        CHART_H = H - MARGIN_TOP - MARGIN_BOTTOM

        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        # Title
        draw.rectangle([0, 0, W, 6], fill=GOLD)
        draw.text((W // 2, 30), "Revenue Dashboard", font=_FONT_TITLE, fill=GOLD, anchor="mt")
        subtitle = f"Last {days} Days • Generated {datetime.utcnow().strftime('%b %d, %Y')}"
        draw.text((W // 2, 75), subtitle, font=_FONT_LABEL, fill=LIGHT_GRAY, anchor="mt")

        # Calculate stats
        total_revenue = sum(d["amount"] for d in data)
        total_txns = sum(d["count"] for d in data)
        avg_daily = total_revenue / max(days, 1)
        max_amount = max((d["amount"] for d in data), default=1) or 1

        # Draw summary stats at top-right area
        stats_y = 25
        stats = [
            (f"Rs.{total_revenue:,.0f}", "Total Revenue", ACCENT_GREEN),
            (f"{total_txns}", "Transactions", BAR_COLOR_TOP),
            (f"Rs.{avg_daily:,.0f}", "Avg/Day", GOLD),
        ]
        stat_x = W - 40
        for val, label, color in reversed(stats):
            draw.text((stat_x, stats_y), val, font=_FONT_STAT, fill=color, anchor="rt")
            draw.text((stat_x, stats_y + 32), label, font=_FONT_STAT_LABEL, fill=LIGHT_GRAY, anchor="rt")
            stat_x -= 200

        # Draw grid lines
        grid_steps = 5
        for i in range(grid_steps + 1):
            y = MARGIN_TOP + CHART_H - (i * CHART_H // grid_steps)
            draw.line([(MARGIN_LEFT, y), (W - MARGIN_RIGHT, y)], fill=GRID_COLOR, width=1)
            val = int(max_amount * i / grid_steps)
            draw.text((MARGIN_LEFT - 10, y), f"Rs.{val}", font=_FONT_VALUE, fill=LIGHT_GRAY, anchor="rm")

        # Draw bars
        num_bars = len(data)
        bar_total_width = CHART_W / num_bars
        bar_width = max(int(bar_total_width * 0.6), 4)
        gap = (bar_total_width - bar_width) / 2

        for i, d in enumerate(data):
            x = int(MARGIN_LEFT + i * bar_total_width + gap)
            bar_height = int((d["amount"] / max_amount) * CHART_H) if d["amount"] > 0 else 0
            y_top = MARGIN_TOP + CHART_H - bar_height
            y_bottom = MARGIN_TOP + CHART_H

            if bar_height > 0:
                # Draw gradient bar
                for py in range(y_top, y_bottom):
                    ratio = (py - y_top) / max(bar_height, 1)
                    r = int(BAR_COLOR_TOP[0] * (1 - ratio) + BAR_COLOR_BOTTOM[0] * ratio)
                    g = int(BAR_COLOR_TOP[1] * (1 - ratio) + BAR_COLOR_BOTTOM[1] * ratio)
                    b = int(BAR_COLOR_TOP[2] * (1 - ratio) + BAR_COLOR_BOTTOM[2] * ratio)
                    draw.line([(x, py), (x + bar_width, py)], fill=(r, g, b))

                # Value label on top of bar
                if d["amount"] > 0:
                    draw.text(
                        (x + bar_width // 2, y_top - 5),
                        f"Rs.{d['amount']:.0f}",
                        font=_FONT_VALUE, fill=WHITE, anchor="mb"
                    )

            # X-axis date labels (show every few days to avoid overlap)
            if num_bars <= 15 or i % (num_bars // 10 + 1) == 0:
                draw.text(
                    (x + bar_width // 2, MARGIN_TOP + CHART_H + 10),
                    d["date"], font=_FONT_VALUE, fill=LIGHT_GRAY, anchor="mt"
                )

        # Bottom accent
        draw.rectangle([0, H - 6, W, H], fill=GOLD)

        buf = BytesIO()
        buf.name = "revenue_chart.png"
        img.save(buf, "PNG", quality=95)
        buf.seek(0)
        return buf

    except Exception as e:
        print(f"Error generating revenue chart: {e}")
        return None
