import time
import schedule
import threading
from src.database import get_expired_subscriptions, deactivate_subscription, get_expiring_soon_subscriptions

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
    print("Sending expiry warnings...")
    
    # Check 3 days left
    expiring_in_3 = get_expiring_soon_subscriptions(days=3)
    for sub in expiring_in_3:
        try:
            msg = "⚠️ *VIP Access Expiring Soon!*\n\nYou only have **3 Days left** on your current subscription.\nRenew early using `💎 Get Premium` to ensure uninterrupted access to the VIP channel!"
            bot.send_message(sub['telegram_id'], msg, parse_mode="Markdown")
        except Exception:
            pass

    # Check 1 day left
    expiring_in_1 = get_expiring_soon_subscriptions(days=1)
    for sub in expiring_in_1:
        try:
            msg = "🚨 *FINAL WARNING: 24 HOURS LEFT*\n\nYour VIP access will be automatically revoked tomorrow. Renew immediately to keep your spot!"
            bot.send_message(sub['telegram_id'], msg, parse_mode="Markdown")
        except Exception:
            pass

def run_scheduler(bot, private_channel_id):
    schedule.every().day.at("00:00").do(check_expired_subscriptions, bot=bot, private_channel_id=private_channel_id)
    schedule.every().day.at("10:00").do(send_expiry_warnings, bot=bot)
    print("Scheduler setup to run at 00:00 (kicks) and 10:00 (warnings) daily.")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_scheduler_thread(bot, private_channel_id):
    print("Starting background scheduler thread...")
    scheduler_thread = threading.Thread(target=run_scheduler, args=(bot, private_channel_id), daemon=True)
    scheduler_thread.start()
