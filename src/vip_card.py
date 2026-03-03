import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def _load_font(size, bold=False):
    """Try to load a font that works on both Windows and Linux."""
    # Font candidates in preference order
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
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
    # Final fallback – Pillow 10.1+ supports size in load_default
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

# Define paths
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

# Generate a default template if one doesn't exist
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "vip_template.png")
if not os.path.exists(TEMPLATE_PATH):
    # Create a dummy luxurious dark gradient background (1000x600 size)
    img = Image.new('RGB', (1000, 600), color=(15, 15, 25))
    draw = ImageDraw.Draw(img)
    # Add some premium gold accents
    draw.rectangle([0, 0, 1000, 20], fill=(212, 175, 55)) # Gold top stripe
    draw.rectangle([0, 580, 1000, 600], fill=(212, 175, 55)) # Gold bottom stripe
    # Add VIP watermark
    font_large = _load_font(100, bold=True)
    draw.text((350, 250), "VIP ACCESS", fill=(30, 30, 45), font=font_large) # subtle watermark
    img.save(TEMPLATE_PATH)

def get_user_profile_photo(bot, user_id):
    """Downloads the highest resolution profile photo of the user."""
    try:
        photos = bot.get_user_profile_photos(user_id)
        if photos.total_count > 0:
            # Get the largest size of their first profile picture
            file_id = photos.photos[0][-1].file_id
            file_info = bot.get_file(file_id)
            
            # Fetch the actual image data from Telegram servers
            token = bot.token
            url = f"https://api.telegram.org/file/bot{token}/{file_info.file_path}"
            response = requests.get(url)
            if response.status_code == 200:
                pfp = Image.open(BytesIO(response.content)).convert("RGBA")
                pfp = pfp.resize((250, 250)) # Ensure standard size
                
                # Make the PFP circular
                mask = Image.new("L", pfp.size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, pfp.size[0], pfp.size[1]), fill=255)
                circular_pfp = Image.new("RGBA", pfp.size)
                circular_pfp.paste(pfp, (0, 0), mask=mask)
                return circular_pfp
    except Exception as e:
        print(f"Failed to fetch profile picture for {user_id}: {e}")
    
    # Fallback to a placeholder circle if no photo exists
    placeholder = Image.new("RGBA", (250, 250), (100, 100, 100, 255))
    mask = Image.new("L", (250, 250), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 250, 250), fill=255)
    circular_placeholder = Image.new("RGBA", (250, 250))
    circular_placeholder.paste(placeholder, (0, 0), mask=mask)
    return circular_placeholder
    
def generate_vip_card(bot, user_id, username, plan_name, expiry_date_str, is_active=False):
    """
    Generates a dynamic image overlaying user details onto the VIP template.
    Returns: A BytesIO object containing the final PNG image.
    """
    try:
        # Load fonts
        font_title = _load_font(60, bold=True)
        font_subtitle = _load_font(40, bold=True)
        font_normal = _load_font(35, bold=False)

        # 1. Base Image
        base = Image.open(TEMPLATE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base)

        # 2. Get and Paste PFP
        pfp = get_user_profile_photo(bot, user_id)
        # Paste on left side, vertically centered
        base.paste(pfp, (70, 175), pfp)
        
        # Draw a gold ring around the PFP
        draw.ellipse([65, 170, 325, 430], outline=(212, 175, 55), width=5)

        # 3. Text Placements (Right side)
        text_x = 380
        
        # Username
        draw.text((text_x, 150), username.upper(), font=font_title, fill=(255, 255, 255))
        
        # User ID
        draw.text((text_x, 230), f"ID: {user_id}", font=font_normal, fill=(180, 180, 200))
        
        # Plan details
        draw.text((text_x, 300), "MEMBERSHIP TIER", font=font_subtitle, fill=(212, 175, 55))
        draw.text((text_x, 350), plan_name.upper(), font=font_title, fill=(255, 255, 255))

        # Status badge
        status = "ACTIVE" if is_active else "INACTIVE"
        status_color = (46, 204, 113) if is_active else (231, 76, 60)
        try:
            draw.rounded_rectangle([text_x, 430, text_x + 200, 480], fill=status_color, radius=10)
        except AttributeError:
            # Pillow < 8.2 fallback
            draw.rectangle([text_x, 430, text_x + 200, 480], fill=status_color)
        draw.text((text_x + 20, 435), status, font=font_normal, fill=(255, 255, 255))

        # Expiry
        if is_active:
            draw.text((text_x + 230, 435), f"EXPIRES: {expiry_date_str.split()[0]}", font=font_normal, fill=(200, 200, 200))


        # 4. Save to buffer
        bio = BytesIO()
        bio.name = 'VIP_Pass.png'
        base.save(bio, 'PNG')
        bio.seek(0)
        return bio
        
    except Exception as e:
        print(f"Error generating VIP card: {e}")
        return None
