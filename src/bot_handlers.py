import uuid
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.database import (
    add_or_update_user, 
    get_active_subscription, 
    get_all_plans, 
    get_plan_by_id, 
    create_subscription,
    add_referral_bonus,
    get_all_users,
    get_admin_stats,
    get_full_analytics_data
)
from io import BytesIO
from src.payments import generate_upi_qr
from src.vip_card import generate_vip_card

def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("💎 Get Premium", callback_data="cmd_subscribe"),
        InlineKeyboardButton("👤 My Profile", callback_data="cmd_profile")
    )
    markup.add(
        InlineKeyboardButton("🎧 Contact Support", callback_data="cmd_support"),
        InlineKeyboardButton("🤝 Refer & Earn", callback_data="cmd_referral")
    )
    return markup
    
def get_admin_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📊 View Stats", callback_data="cmd_admin_stats"),
        InlineKeyboardButton("📣 Broadcast Message", callback_data="cmd_admin_broadcast")
    )
    markup.add(
        InlineKeyboardButton("💾 Export Analytics", callback_data="cmd_admin_export"),
        InlineKeyboardButton("🔙 Exit Admin Mode", callback_data="cmd_admin_exit")
    )
    return markup
    
def send_msg_with_optional_image(bot, chat_id, image_url, text, **kwargs):
    if image_url and image_url.strip():
        try:
            return bot.send_photo(chat_id, photo=image_url, caption=text, **kwargs)
        except Exception as e:
            print(f"Failed to send image {image_url}: {e}. Falling back to text.")
            return bot.send_message(chat_id, text, **kwargs)
    else:
        return bot.send_message(chat_id, text, **kwargs)

def register_handlers(bot, upi_id, private_channel_id, admin_id, start_img="", help_img="", profile_img="", plan_img="", support_img=""):

    @bot.message_handler(commands=['start'])
    def command_start(message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        referrer_id = None
        args = message.text.split()
        if len(args) > 1 and args[1].startswith('ref_'):
            try:
                referrer_id = int(args[1].split('_')[1])
                if referrer_id == user_id:
                    referrer_id = None
            except (ValueError, IndexError):
                pass
                
        add_or_update_user(user_id, username, referrer_id)
        
        welcome_text = (
            f"Hello {username}! 👋\n\n"
            "Welcome to the *Premium VIP Hub*.\n"
            "Get instant access to our exclusive content and community.\n\n"
            "👇 Please use the menu below to navigate."
        )
        send_msg_with_optional_image(
            bot, message.chat.id, start_img, welcome_text, 
            parse_mode="Markdown", reply_markup=get_main_keyboard()
        )

    @bot.message_handler(commands=['help'])
    def command_help(message):
        help_text = (
            "📌 *Quick Guide:*\n\n"
            "🔹 *Get Premium:* Browse plans and buy access.\n"
            "🔹 *My Profile:* Check your subscription status.\n"
            "🔹 *Support:* Talk directly with our admin team.\n"
            "🔹 *Refer & Earn:* Get a custom link to earn free VIP access!\n\n"
            "You can also use /start at any time to refresh the menu."
        )
        send_msg_with_optional_image(bot, message.chat.id, help_img, help_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

    def _handle_profile(chat_id, user_id, username):
        sub = get_active_subscription(user_id)
        
        bot.send_message(chat_id, "⏳ Generating your Premium VIP Pass...")
        
        if sub:
            plan_name = sub["plan_name"]
            end_date_str = sub["end_date"].strftime("%Y-%m-%d %H:%M:%S")
            is_active = True
            msg = f"✅ *Active VIP Member*\n\n🛡️ *Current Plan:* {plan_name}\n⏳ *Valid Until:* `{end_date_str} UTC`"
        else:
            plan_name = "NONE"
            end_date_str = "N/A"
            is_active = False
            msg = "❌ *No Active Subscription*\n\nYou currently don't have access to the VIP channel.\nTap '💎 Get Premium' below to view our plans."
            
        # Generate the dynamic image
        card_io = generate_vip_card(bot, user_id, username, plan_name, end_date_str, is_active)
        
        if card_io:
            bot.send_photo(chat_id, photo=card_io, caption=msg, parse_mode="Markdown")
        else:
            # Fallback to plain text if image generation fails for some reason
            send_msg_with_optional_image(bot, chat_id, profile_img, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['my_subscription', 'profile'])
    def command_my_subscription(message):
        username = message.from_user.username or message.from_user.first_name
        _handle_profile(message.chat.id, message.from_user.id, username)

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_profile")
    def callback_profile(call):
        bot.answer_callback_query(call.id)
        username = call.from_user.username or call.from_user.first_name
        _handle_profile(call.message.chat.id, call.from_user.id, username)

    def _handle_subscribe(chat_id):
        plans = get_all_plans()
        if not plans:
            bot.send_message(chat_id, "⚠️ No VIP plans are currently available.")
            return

        markup = InlineKeyboardMarkup(row_width=1)
        for plan in plans:
            btn_text = f"🔥 {plan['name']} - ₹{plan['price']} ({plan['duration_days']} Days)"
            markup.add(InlineKeyboardButton(btn_text, callback_data=f"buy_{plan['id']}"))
            
        send_msg_with_optional_image(bot, chat_id, plan_img, "✨ *Choose Your VIP Pass:*\n\nSelect a plan below to generate your secure payment QR.", parse_mode="Markdown", reply_markup=markup)

    @bot.message_handler(commands=['subscribe', 'premium'])
    def command_subscribe(message):
        _handle_subscribe(message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_subscribe")
    def callback_subscribe(call):
        bot.answer_callback_query(call.id)
        _handle_subscribe(call.message.chat.id)

    def _handle_referral(chat_id, user_id):
        bot_info = bot.get_me()
        bot_username = bot_info.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        msg = (
            "🤝 *Refer & Earn VIP Access*\n\n"
            "Share your unique referral link below with friends, groups, or channels.\n"
            "Whenever someone uses your link and buys *any* subscription plan, you automatically get **+7 Days** of VIP access added to your account for free!\n\n"
            f"🔗 *Your Unique Link:*\n`{ref_link}`"
        )
        
        markup = InlineKeyboardMarkup()
        # Allows user to pick a chat from their contacts to share the link to
        markup.add(InlineKeyboardButton("📤 Share Referral Link", url=f"https://t.me/share/url?url={ref_link}&text=Join%20the%20VIP%20Premium%20Hub!"))
        
        bot.send_message(chat_id, msg, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_referral")
    def callback_referral(call):
        bot.answer_callback_query(call.id)
        _handle_referral(call.message.chat.id, call.from_user.id)

    # ---------------- ADMIN COMMANDS (DASHBOARD & BROADCAST) ---------------- #
    @bot.message_handler(commands=['admin'])
    def command_admin(message):
        if str(message.from_user.id) != str(admin_id):
            return
        bot.send_message(message.chat.id, "👑 *Admin Control Panel*\n\nWelcome back. Please select an option from the menu below.", parse_mode="Markdown", reply_markup=get_admin_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_exit")
    def callback_admin_exit(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id, "Exited Admin Mode.")
        bot.send_message(call.message.chat.id, "Exited Admin Mode. Main Menu:", reply_markup=get_main_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_stats")
    def callback_view_stats(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        stats = get_admin_stats()
        text = (
            "📊 *Business Dashboard*\n\n"
            f"👥 *Total Registered Users:* {stats['total_users']}\n"
            f"🔥 *Active Subscriptions:* {stats['active_subs']}\n"
            f"💰 *Current Estimated Revenue:* ₹{stats['current_revenue']}\n"
        )
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_export")
    def callback_export_analytics(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id, "Generating report...")
        bot.send_message(call.message.chat.id, "⏳ Generating HTML Analytics Report... Please wait.")
        
        data = get_full_analytics_data()
        
        # Build HTML
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Premium Bot Analytics Report</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; margin: 40px; }
                h1 { color: #2c3e50; text-align: center; margin-bottom: 5px; }
                h3 { color: #7f8c8d; text-align: center; margin-bottom: 30px; font-weight: normal; }
                table { width: 100%; border-collapse: collapse; background-color: #fff; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
                th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #3498db; color: white; text-transform: uppercase; font-size: 14px; letter-spacing: 0.5px; }
                tr:hover { background-color: #f1f1f1; }
                .status-active { color: #27ae60; font-weight: bold; }
                .status-expired { color: #e74c3c; font-weight: bold; }
                .status-inactive { color: #95a5a6; }
                .footer { text-align: center; margin-top: 30px; color: #95a5a6; font-size: 13px; }
            </style>
        </head>
        <body>
            <h1>💎 Premium Bot Analytics</h1>
            <h3>Detailed User & Subscription Report</h3>
            <table>
                <thead>
                    <tr>
                        <th>Telegram ID</th>
                        <th>Username</th>
                        <th>Invited By (ID)</th>
                        <th>Total Referrals</th>
                        <th>Current Plan</th>
                        <th>Status</th>
                        <th>Expiry Date (UTC)</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for row in data:
            status_class = "status-inactive"
            if row['status'] == 'Active':
                status_class = 'status-active'
            elif row['status'] == 'Expired':
                status_class = 'status-expired'
                
            html_content += f"""
                    <tr>
                        <td><code>{row['telegram_id']}</code></td>
                        <td>{row['username']}</td>
                        <td>{row['referrer_id']}</td>
                        <td>{row['referral_count']}</td>
                        <td>{row['plan_name']}</td>
                        <td class="{status_class}">{row['status']}</td>
                        <td>{row['end_date']}</td>
                    </tr>
            """
            
        html_content += f"""
                </tbody>
            </table>
            <div class="footer">
                Generated automatically by your Telegram Bot at {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
            </div>
        </body>
        </html>
        """
        
        bio = BytesIO(html_content.encode('utf-8'))
        bio.name = f"Analytics_Report_{datetime.utcnow().strftime('%Y%m%d')}.html"
        
        bot.send_document(
            call.message.chat.id, 
            document=bio, 
            caption="✅ *Analytics Report Generated Successfully!*\n\nDownload the attached HTML file and open it in any web browser to view your user data.", 
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_broadcast")
    def callback_broadcast_init(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "📣 *Broadcast Mode*\n\nPlease type the message you want to send to ALL registered users.\n(Type `cancel` to abort).", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_broadcast)

    def process_broadcast(message):
        if str(message.from_user.id) != str(admin_id):
            return
            
        if message.text and message.text.lower() == 'cancel':
            bot.send_message(message.chat.id, "Broadcast cancelled.", reply_markup=get_admin_keyboard())
            return
            
        users = get_all_users()
        success = 0
        failed = 0
        
        bot.send_message(message.chat.id, f"⏳ Broadcasting to {len(users)} users... Please wait.")
        for uid in users:
            try:
                if message.photo:
                    bot.send_photo(uid, photo=message.photo[-1].file_id, caption=message.caption, parse_mode="Markdown")
                elif message.document:
                    bot.send_document(uid, document=message.document.file_id, caption=message.caption, parse_mode="Markdown")
                else:
                    bot.send_message(uid, message.text, parse_mode="Markdown")
                success += 1
            except Exception:
                failed += 1
                
        bot.send_message(message.chat.id, f"✅ *Broadcast Complete*\n\nSuccessfully sent to: {success} users.\nFailed (Blocked/Deleted): {failed} users.", parse_mode="Markdown", reply_markup=get_admin_keyboard())


    # ---------------- SUPPORT SYSTEM ---------------- #
    def _handle_support(chat_id):
        msg = send_msg_with_optional_image(bot, chat_id, support_img, "📝 *Support Desk*\n\nPlease type your question below in a single message.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_support_message)

    @bot.message_handler(commands=['support'])
    def command_support(message):
        _handle_support(message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_support")
    def callback_support(call):
        bot.answer_callback_query(call.id)
        _handle_support(call.message.chat.id)

    def process_support_message(message):
        msg_text = message.text or message.caption or "[Non-text message]"
        if msg_text in ["/start", "/help", "/admin"]:
            bot.send_message(message.chat.id, "Support request cancelled. Re-routing...")
            return

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        bot.send_message(message.chat.id, "✅ Your message has been routed to the Admin team. We will get back to you soon.")
        
        admin_msg = f"🆘 *New Support Ticket*\n\n👤 *From:* {username} (`{user_id}`)\n📝 *Message:*\n{msg_text}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("💬 Reply to User", callback_data=f"supreply_{user_id}"))
        
        try:
            bot.send_message(admin_id, admin_msg, parse_mode="Markdown", reply_markup=markup)
        except Exception:
            bot.send_message(message.chat.id, "❌ Sorry, the support system is currently unavailable.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith('supreply_'))
    def admin_support_reply_init(call):
        if str(call.from_user.id) != str(admin_id): return
        target_user_id = call.data.split('_')[1]
        original_msg = "\n".join(call.message.text.split('\n')[3:]) 
        msg = bot.send_message(admin_id, f"Type your reply to user `{target_user_id}` below.\n\n_Replying to:_\n{original_msg}", parse_mode="Markdown")
        bot.register_next_step_handler(msg, admin_support_reply_send, target_user_id, original_msg)
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        
    def admin_support_reply_send(message, target_user_id, original_msg):
        try:
            bot.send_message(target_user_id, f"👨‍💻 *Admin Reply:*\n\n{message.text}\n\n〰️〰️〰️\n_Your Original Message:_\n{original_msg}", parse_mode="Markdown")
            bot.send_message(message.chat.id, "✅ Reply successfully delivered to user.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Failed to reach user: {e}")

    # ---------------- PAYMENTS & ADMIN VERIFICATION ---------------- #
    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
    def process_plan_selection(call):
        plan_id = int(call.data.split('_')[1])
        plan = get_plan_by_id(plan_id)
        if not plan: return
            
        tx_ref = str(uuid.uuid4())[:8].upper()
        qr_image = generate_upi_qr(upi_id, plan['price'], tx_ref)
        caption = f"🛒 *Checkout: {plan['name']}*\n\n💸 *Amount:* `₹{plan['price']}`\n🏦 *UPI ID:* `{upi_id}` (Tap to copy)\n📝 *Ref ID:* `{tx_ref}`\n\nPlease scan the QR code or copy the UPI ID to pay."
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📸 Send Screenshot", callback_data=f"ss_{plan_id}_{tx_ref}"))
        bot.send_photo(call.message.chat.id, photo=qr_image, caption=caption, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('ss_'))
    def ask_for_screenshot(call):
        data = call.data.split('_')
        msg = bot.send_message(call.message.chat.id, "📸 Please *upload a screenshot* of your successful payment.\n\nMake sure the transaction ID is clearly visible.", parse_mode="Markdown")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.register_next_step_handler(msg, process_screenshot_upload, data[1], data[2])

    def process_screenshot_upload(message, plan_id, tx_ref):
        if not message.photo and not message.document:
            bot.send_message(message.chat.id, "❌ I did not receive an image. Please start the /subscribe process again.")
            return
            
        bot.send_message(message.chat.id, "⏳ Your payment screenshot has been sent to the Admin for verification.")
        plan = get_plan_by_id(int(plan_id))
        admin_caption = f"🚨 *New Payment Verification*\n\n👤 *User:* {message.from_user.username} (`{message.from_user.id}`)\n📦 *Plan:* {plan['name']}\n💸 *Amount Expected:* ₹{plan['price']}\n📝 *Ref ID:* `{tx_ref}`\n\nPlease verify this screenshot."
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("✅ Approve", callback_data=f"approve_{message.from_user.id}_{plan_id}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{message.from_user.id}"))
        
        if message.photo:
            bot.send_photo(admin_id, photo=message.photo[-1].file_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")
        elif message.document:
            bot.send_document(admin_id, document=message.document.file_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")


    @bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
    def admin_verification_decision(call):
        if str(call.from_user.id) != str(admin_id): return
        data = call.data.split('_')
        action = data[0]
        target_user_id = int(data[1])
        
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

        if action == "approve":
            plan_id = int(data[2])
            new_sub = create_subscription(target_user_id, plan_id)
            if not new_sub: return bot.send_message(admin_id, f"❌ Failed to create subscription for user {target_user_id}.")
                
            try:
                invite_link = bot.create_chat_invite_link(chat_id=private_channel_id, member_limit=1).invite_link
                success_msg = f"🎉 *Payment Verified!*\n\nYour payment was approved. Thank you for subscribing to the *{new_sub['plan_name']}* plan.\nYour access is valid until: `{new_sub['end_date'].strftime('%Y-%m-%d %H:%M UTC')}`\n\n👉 [Click here to join the private channel]({invite_link})\n\n_(This link can only be used once.)_"
                bot.send_message(target_user_id, success_msg, parse_mode="Markdown", disable_web_page_preview=True)
                try:
                    bot.edit_message_caption(caption=f"{call.message.caption or ''}\n\n*STATUS: ✅ APPROVED*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
                except Exception:
                    pass  # Message may not have a caption
                bot.answer_callback_query(call.id, "Payment Approved.")
                
                # Check for referral reward
                if new_sub.get("referrer_id"):
                    rewarded = add_referral_bonus(new_sub["referrer_id"], bonus_days=7)
                    if rewarded:
                        try:
                            ref_msg = "🎉 *Referral Bonus Unlocked!*\n\nSomeone just used your unique referral link to buy a subscription!\nWe have added **+7 Days** of VIP access to your account as a thank you! 📈"
                            bot.send_message(new_sub["referrer_id"], ref_msg, parse_mode="Markdown")
                        except Exception as e:
                            print(f"Could not message referrer: {e}")
                            
            except Exception as e:
                bot.send_message(admin_id, f"❌ Error generating invite link: {e}")
                
        elif action == "reject":
            try:
                bot.edit_message_caption(caption=f"{call.message.caption or ''}\n\n*STATUS: ❌ REJECTED*", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")
            except Exception:
                pass  # Message may not have a caption
            reject_msg = "❌ *Payment Verification Failed*\n\nYour payment screenshot was rejected by the Admin. This usually happens if the transaction ID is invalid, missing, or the amount is incorrect.\n\nPlease try again or use the 🎧 Contact Support option if you think this is a mistake."
            bot.send_message(target_user_id, reject_msg, parse_mode="Markdown")
            bot.answer_callback_query(call.id, "Payment Rejected.")
