import time
import schedule
import threading
from src.database import (
    get_expired_subscriptions, deactivate_subscription,
    get_expiring_soon_subscriptions, get_users_for_drip,
    get_due_broadcasts, mark_broadcast_sent, get_all_users
)

def check_expired_subscriptions(bot, private_channel_id):
    print("Checking for expired subscriptions...")
    expired_subs = get_expired_subscriptions()
    
    for sub in expired_subs:
        telegram_id = sub['telegram_id']
        sub_id = sub['sub_id']
        
        try:
            bot.ban_chat_member(chat_id=int(private_channel_id), user_id=telegram_id)
            bot.unban_chat_member(chat_id=int(private_channel_id), user_id=telegram_id)
            
            try:
                bot.send_message(
                    chat_id=telegram_id, 
                    text="⚠️ Your subscription has expired. You have been removed from the VIP channel. Tap '💎 Get Premium' to renew!"
                )
            except Exception as e:
                print(f"Could not send DM to user {telegram_id}: {e}")
                
            deactivate_subscription(sub_id)
            print(f"User {telegram_id} subscription {sub_id} expired and processed.")
            
        except Exception as e:
            print(f"Error processing expired subscription for {telegram_id}: {e}")

def send_expiry_warnings(bot):
    """Send expiry warnings with auto-renewal QR buttons (#8)."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    print("Sending expiry warnings...")
    
    # Check 3 days left
    expiring_in_3 = get_expiring_soon_subscriptions(days=3)
    for sub in expiring_in_3:
        try:
            # Find user's current plan to offer 1-tap renewal
            active = get_active_subscription(sub['telegram_id'])
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔄 Renew Now — 1 Tap", callback_data="cmd_subscribe"))
            
            msg = (
                "⚠️ *VIP Access Expiring Soon!*\n\n"
                "You only have **3 Days left** on your current subscription.\n"
                "Renew early using the button below to ensure uninterrupted access to the VIP channel!"
            )
            bot.send_message(sub['telegram_id'], msg, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass

    # Check 1 day left — urgent with renewal button
    expiring_in_1 = get_expiring_soon_subscriptions(days=1)
    for sub in expiring_in_1:
        try:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔄 Renew Now — 1 Tap", callback_data="cmd_subscribe"))
            
            msg = (
                "🚨 *FINAL WARNING: 24 HOURS LEFT*\n\n"
                "Your VIP access will be automatically revoked tomorrow.\n"
                "Renew immediately to keep your spot!"
            )
            bot.send_message(sub['telegram_id'], msg, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            pass


def run_drip_campaign(bot):
    """Send targeted upgrade nudges to free users (#27)."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    print("Running drip campaign...")

    drip_messages = {
        1: (
            "👋 *Hey there!*\n\n"
            "Thanks for joining us yesterday! Did you know our VIP members get "
            "exclusive access to premium content and a private community?\n\n"
            "🔥 Plans start at just *₹99* — check them out!"
        ),
        3: (
            "💡 *Quick reminder!*\n\n"
            "You've been with us for 3 days now, but you're missing out on the best part!\n"
            "Our VIP channel is where the real action happens.\n\n"
            "⚡ Unlock VIP access today — it only takes a minute!"
        ),
        7: (
            "🎯 *One week in!*\n\n"
            "You've been here for a whole week — clearly you like what we do! 😄\n"
            "Imagine getting *10x more* with our VIP membership.\n\n"
            "🏆 Join hundreds of VIP members today.\n"
            "Don't miss out — upgrade now!"
        ),
    }

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("💎 View Plans & Subscribe", callback_data="cmd_subscribe"))

    for days, message in drip_messages.items():
        users = get_users_for_drip(days)
        for user in users:
            try:
                bot.send_message(user["telegram_id"], message, parse_mode="Markdown", reply_markup=markup)
                print(f"Drip day-{days} sent to {user['telegram_id']}")
            except Exception as e:
                print(f"Drip failed for {user['telegram_id']}: {e}")


def process_scheduled_broadcasts(bot):
    """Check and send any due scheduled broadcasts (#28)."""
    print("Checking scheduled broadcasts...")
    due = get_due_broadcasts()

    if not due:
        return

    all_users = get_all_users()
    
    for broadcast in due:
        msg_text = broadcast.get("message_text", "")
        media_type = broadcast.get("media_type")
        media_file_id = broadcast.get("media_file_id")
        success = 0
        failed = 0

        for uid in all_users:
            try:
                if media_type == "photo" and media_file_id:
                    bot.send_photo(uid, photo=media_file_id, caption=msg_text, parse_mode="Markdown")
                elif media_type == "document" and media_file_id:
                    bot.send_document(uid, document=media_file_id, caption=msg_text, parse_mode="Markdown")
                elif msg_text:
                    bot.send_message(uid, msg_text, parse_mode="Markdown")
                success += 1
            except Exception:
                failed += 1

        mark_broadcast_sent(broadcast["_id"])
        print(f"Scheduled broadcast sent: {success} success, {failed} failed")

        # Notify admin
        admin_id = broadcast.get("admin_id")
        if admin_id:
            try:
                bot.send_message(
                    admin_id,
                    f"✅ *Scheduled Broadcast Sent!*\n\n"
                    f"📤 Delivered: {success}\n❌ Failed: {failed}\n"
                    f"📝 Message: {msg_text[:100]}...",
                    parse_mode="Markdown"
                )
            except Exception:
                pass


def run_scheduler(bot, private_channel_id):
    # Existing daily jobs
    schedule.every().day.at("00:00").do(check_expired_subscriptions, bot=bot, private_channel_id=private_channel_id)
    schedule.every().day.at("10:00").do(send_expiry_warnings, bot=bot)
    # Drip campaign — runs daily at 11:00 UTC
    schedule.every().day.at("11:00").do(run_drip_campaign, bot=bot)
    # Scheduled broadcasts — check every 2 minutes
    schedule.every(2).minutes.do(process_scheduled_broadcasts, bot=bot)

    print("Scheduler setup: 00:00 (kicks), 10:00 (warnings+renewal), 11:00 (drip), every 2min (scheduled broadcasts)")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_scheduler_thread(bot, private_channel_id):
    print("Starting background scheduler thread...")
    scheduler_thread = threading.Thread(target=run_scheduler, args=(bot, private_channel_id), daemon=True)
    scheduler_thread.start()
