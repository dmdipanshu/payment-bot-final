import os
import telebot
from flask import Flask, request, jsonify, render_template
from src.database import init_db
from src.bot_handlers import register_handlers
from src.koyeb_scheduler import start_scheduler_thread

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "-1001234567890"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# Image URLs
START_IMAGE_URL = os.getenv("START_IMAGE_URL", "")
HELP_IMAGE_URL = os.getenv("HELP_IMAGE_URL", "")
PROFILE_IMAGE_URL = os.getenv("PROFILE_IMAGE_URL", "")
PLAN_IMAGE_URL = os.getenv("PLAN_IMAGE_URL", "")
SUPPORT_IMAGE_URL = os.getenv("SUPPORT_IMAGE_URL", "")

if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
    print("Warning: Missing or invalid BOT_TOKEN")

# Validate Razorpay credentials
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    print("⚠️ Warning: RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set. Payments will not work.")
if not RAZORPAY_WEBHOOK_SECRET:
    print("⚠️ Warning: RAZORPAY_WEBHOOK_SECRET not set. Webhook signature verification disabled.")

bot = telebot.TeleBot(BOT_TOKEN)

register_handlers(
    bot, PRIVATE_CHANNEL_ID, ADMIN_ID,
    START_IMAGE_URL, HELP_IMAGE_URL, PROFILE_IMAGE_URL, 
    PLAN_IMAGE_URL, SUPPORT_IMAGE_URL
)

# Explicitly remove commands to clear the Telegram menu button across all scopes
bot.delete_my_commands()
bot.delete_my_commands(scope=telebot.types.BotCommandScopeAllPrivateChats())
bot.delete_my_commands(scope=telebot.types.BotCommandScopeAllGroupChats())
bot.delete_my_commands(scope=telebot.types.BotCommandScopeAllChatAdministrators())

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

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

# ---------- RAZORPAY WEBHOOK ENDPOINT ---------- #
@app.route('/razorpay/webhook', methods=['POST'])
def razorpay_webhook():
    """Receives Razorpay payment confirmations and auto-verifies payments."""
    try:
        from src.razorpay_client import verify_webhook_signature
        from src.pending_payments import find_pending_by_qr_id, is_event_already_processed

        # 1. Get raw body and signature
        raw_body = request.get_data().decode('utf-8')
        signature = request.headers.get('x-razorpay-signature', '')

        if not RAZORPAY_WEBHOOK_SECRET:
            print("WARNING: RAZORPAY_WEBHOOK_SECRET not set, skipping signature check")
        else:
            # 2. Verify signature
            verify_webhook_signature(raw_body, signature, RAZORPAY_WEBHOOK_SECRET)

        # 3. Parse event
        event_data = request.json
        event_type = event_data.get('event', '')

        print(f"Razorpay webhook received: {event_type}")

        if event_type == 'qr_code.credited':
            # Extract QR code ID and payment ID
            qr_entity = event_data.get('payload', {}).get('qr_code', {}).get('entity', {})
            payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})

            qr_id = qr_entity.get('id', '')
            payment_id = payment_entity.get('id', '')

            print(f"Payment {payment_id} received for QR {qr_id}")

            # Idempotency check
            if is_event_already_processed(qr_id):
                print(f"QR {qr_id} already processed, skipping.")
                return jsonify({"status": "already_processed"}), 200

            # Find pending payment
            pending = find_pending_by_qr_id(qr_id)
            if pending:
                # Fulfill the payment (create subscription, send invite link)
                bot._fulfill_payment(None, pending, qr_id, payment_id)
                print(f"Payment fulfilled for user {pending['telegram_id']}")
            else:
                print(f"No pending payment found for QR {qr_id}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"Razorpay webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

def setup_webhook():
    try:
        APP_URL = os.getenv("KOYEB_PUBLIC_URL")
        # Try a few times to deal with transient ConnectionResetError on Koyeb startup
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                bot.remove_webhook()
                break
            except Exception as e:
                print(f"Failed to remove webhook (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(2)
        
        if APP_URL:
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

# Ensure plans are created automatically on startup
from src.plan import add_dummy_plans
add_dummy_plans()

def main_run():
    # If the app is run via gunicorn, __name__ != '__main__', but this module is loaded.
    # In that case, we only want to setup the environment (which we did) and setup the webhook.
    APP_URL = os.getenv("KOYEB_PUBLIC_URL")
    if APP_URL:
        print("Configuring for webhook mode...")
        start_scheduler_thread(bot, PRIVATE_CHANNEL_ID)
        setup_webhook()
        # If run directly via python main.py, we must start the Flask app
        if __name__ == '__main__':
            port = int(os.environ.get("PORT", 8000))
            print(f"Starting Flask server on port {port}...")
            app.run(host="0.0.0.0", port=port)
    else:
        print("Running in local mode with infinity_polling...")
        start_scheduler_thread(bot, PRIVATE_CHANNEL_ID)
        try:
            bot.remove_webhook()
        except Exception as e:
            print(f"Error removing webhook before polling: {e}")
        bot.infinity_polling()

if __name__ == '__main__':
    main_run()
else:
    # Running under gunicorn or another WSGI server
    APP_URL = os.getenv("KOYEB_PUBLIC_URL")
    start_scheduler_thread(bot, PRIVATE_CHANNEL_ID)
    setup_webhook()
