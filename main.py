import os
import telebot
from flask import Flask, request, jsonify
from src.database import init_db
from src.bot_handlers import register_handlers
from src.koyeb_scheduler import start_scheduler_thread

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
UPI_ID = os.getenv("UPI_ID", "yourname@upi")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "-1001234567890"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Image URLs
START_IMAGE_URL = os.getenv("START_IMAGE_URL", "")
HELP_IMAGE_URL = os.getenv("HELP_IMAGE_URL", "")
PROFILE_IMAGE_URL = os.getenv("PROFILE_IMAGE_URL", "")
PLAN_IMAGE_URL = os.getenv("PLAN_IMAGE_URL", "")
SUPPORT_IMAGE_URL = os.getenv("SUPPORT_IMAGE_URL", "")

if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
    print("Warning: Missing or invalid BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(
    bot, UPI_ID, PRIVATE_CHANNEL_ID, ADMIN_ID,
    START_IMAGE_URL, HELP_IMAGE_URL, PROFILE_IMAGE_URL, 
    PLAN_IMAGE_URL, SUPPORT_IMAGE_URL
)

app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return jsonify({"error": "Invalid Content-Type"}), 403

def setup_webhook():
    try:
        APP_URL = os.getenv("KOYEB_PUBLIC_URL")
        bot.remove_webhook()
        if APP_URL:
            import time
            time.sleep(1)
            webhook_url = f"{APP_URL.rstrip('/')}/{BOT_TOKEN}"
            bot.set_webhook(url=webhook_url)
            print(f"Webhook set to {webhook_url}")
        else:
            print("Warning: KOYEB_PUBLIC_URL not set. Webhook not configured.")
    except Exception as e:
        print(f"Error setting up webhook: {e}")

if not init_db():
    print("\n❌ Cannot start bot without a database connection.")
    print("   Please check your MONGO_URI in the .env file.")
    print("   Make sure your MongoDB Atlas cluster is active and your IP is whitelisted.")
    import sys
    sys.exit(1)

if __name__ == '__main__':
    print("Running in local mode with infinity_polling...")
    start_scheduler_thread(bot, PRIVATE_CHANNEL_ID)
    bot.remove_webhook()
    bot.infinity_polling()
else:
    start_scheduler_thread(bot, PRIVATE_CHANNEL_ID)
    setup_webhook()
