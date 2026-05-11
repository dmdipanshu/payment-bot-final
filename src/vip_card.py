import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from functools import lru_cache
import threading

# ---- CACHING ---- #
_pfp_cache = {}  # {user_id: (circular_image, timestamp)}
_PFP_CACHE_TTL = 300  # 5 minutes

_font_cache = {}

def _load_font(size, bold=False):
    """Load font with caching — avoids disk I/O on every call."""
    cache_key = (size, bold)
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    
    if bold:
        candidates = [
            "arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
    for font_path in candidates:
        try:
            font = ImageFont.truetype(font_path, size)
            _font_cache[cache_key] = font
            return font
        except (IOError, OSError):
            continue
    try:
        font = ImageFont.load_default(size=size)
    except TypeError:
        font = ImageFont.load_default()
    _font_cache[cache_key] = font
    return font

# Pre-load all fonts at import time
FONT_TITLE = _load_font(60, bold=True)
FONT_SUBTITLE = _load_font(40, bold=True)
FONT_NORMAL = _load_font(35, bold=False)

# Define paths
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# Generate a default template if one doesn't exist
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "vip_template.png")
if not os.path.exists(TEMPLATE_PATH):
    img = Image.new('RGB', (1000, 600), color=(15, 15, 25))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 1000, 20], fill=(212, 175, 55))
    draw.rectangle([0, 580, 1000, 600], fill=(212, 175, 55))
    font_large = _load_font(100, bold=True)
    draw.text((350, 250), "VIP ACCESS", fill=(30, 30, 45), font=font_large)
    img.save(TEMPLATE_PATH)

# Pre-load template into memory (avoid disk read every time)
_TEMPLATE_IMAGE = Image.open(TEMPLATE_PATH).convert("RGBA")

# Pre-create placeholder PFP (reused for users without profile photos)
_placeholder = Image.new("RGBA", (250, 250), (100, 100, 100, 255))
_mask = Image.new("L", (250, 250), 0)
_draw_mask = ImageDraw.Draw(_mask)
_draw_mask.ellipse((0, 0, 250, 250), fill=255)
_PLACEHOLDER_PFP = Image.new("RGBA", (250, 250))
_PLACEHOLDER_PFP.paste(_placeholder, (0, 0), mask=_mask)


def get_user_profile_photo(bot, user_id):
    """Downloads profile photo with 5-minute cache."""
    import time
    
    # Check cache first
    if user_id in _pfp_cache:
        cached_img, cached_time = _pfp_cache[user_id]
        if time.time() - cached_time < _PFP_CACHE_TTL:
            return cached_img.copy()
    
    try:
        photos = bot.get_user_profile_photos(user_id)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            file_info = bot.get_file(file_id)
            
            token = bot.token
            url = f"https://api.telegram.org/file/bot{token}/{file_info.file_path}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                pfp = Image.open(BytesIO(response.content)).convert("RGBA")
                pfp = pfp.resize((250, 250), Image.LANCZOS)
                
                mask = Image.new("L", pfp.size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, pfp.size[0], pfp.size[1]), fill=255)
                circular_pfp = Image.new("RGBA", pfp.size)
                circular_pfp.paste(pfp, (0, 0), mask=mask)
                
                # Cache result
                _pfp_cache[user_id] = (circular_pfp, time.time())
                return circular_pfp.copy()
    except Exception as e:
        print(f"Failed to fetch profile picture for {user_id}: {e}")
    
    return _PLACEHOLDER_PFP.copy()

    
def generate_vip_card(bot, user_id, username, plan_name, expiry_date_str, is_active=False):
    """
    Generates VIP card image — optimized with pre-loaded template, cached fonts,
    and cached profile photos.
    """
    try:
        # 1. Copy pre-loaded template (fast, no disk I/O)
        base = _TEMPLATE_IMAGE.copy()
        draw = ImageDraw.Draw(base)

        # 2. Get PFP (cached)
        pfp = get_user_profile_photo(bot, user_id)
        base.paste(pfp, (70, 175), pfp)
        
        # Draw gold ring
        draw.ellipse([65, 170, 325, 430], outline=(212, 175, 55), width=5)

        # 3. Text (using pre-loaded fonts)
        text_x = 380
        draw.text((text_x, 150), username.upper(), font=FONT_TITLE, fill=(255, 255, 255))
        draw.text((text_x, 230), f"ID: {user_id}", font=FONT_NORMAL, fill=(180, 180, 200))
        draw.text((text_x, 300), "MEMBERSHIP TIER", font=FONT_SUBTITLE, fill=(212, 175, 55))
        draw.text((text_x, 350), plan_name.upper(), font=FONT_TITLE, fill=(255, 255, 255))

        # Status badge
        status = "ACTIVE" if is_active else "INACTIVE"
        status_color = (46, 204, 113) if is_active else (231, 76, 60)
        try:
            draw.rounded_rectangle([text_x, 430, text_x + 200, 480], fill=status_color, radius=10)
        except AttributeError:
            draw.rectangle([text_x, 430, text_x + 200, 480], fill=status_color)
        draw.text((text_x + 20, 435), status, font=FONT_NORMAL, fill=(255, 255, 255))

        if is_active:
            draw.text((text_x + 230, 435), f"EXPIRES: {expiry_date_str.split()[0]}", font=FONT_NORMAL, fill=(200, 200, 200))
        else:
            draw.text((text_x + 240, 435), f"UPGRADE NOW", font=FONT_NORMAL, fill=(200, 200, 200))

        # 4. Save to buffer
        bio = BytesIO()
        bio.name = 'VIP_Pass.png'
        base.save(bio, 'PNG')
        bio.seek(0)
        return bio
        
    except Exception as e:
        print(f"Error generating VIP card: {e}")
        return None
