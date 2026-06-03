import html as html_escape
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from src.database import (
    add_or_update_user, 
    get_active_subscription, 
    get_all_plans, 
    get_plan_by_id, 
    create_subscription,
    add_referral_bonus,
    get_all_users,
    get_admin_stats,
    get_full_analytics_data,
    create_plan,
    update_plan,
    delete_plan,
    get_subscription_with_countdown,
    create_scheduled_broadcast,
    get_pending_broadcasts,
    cancel_scheduled_broadcast,
)
from io import BytesIO
from src.payments import generate_razorpay_qr
from src.vip_card import generate_vip_card
from src.receipt import generate_receipt_image
from src.revenue_chart import generate_revenue_chart

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
        InlineKeyboardButton("📈 Revenue Chart", callback_data="cmd_admin_revenue")
    )
    markup.add(
        InlineKeyboardButton("📣 Broadcast Now", callback_data="cmd_admin_broadcast"),
        InlineKeyboardButton("⏰ Schedule Broadcast", callback_data="cmd_admin_schedule")
    )
    markup.add(
        InlineKeyboardButton("📌 Manage Plans", callback_data="cmd_admin_plans"),
        InlineKeyboardButton("💾 Export Analytics", callback_data="cmd_admin_export")
    )
    markup.add(
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

def register_handlers(bot, private_channel_id, admin_id, start_img="", help_img="", profile_img="", plan_img="", support_img=""):

    # Cache bot.get_me() — called once, reused forever
    _bot_info_cache = {}
    def _get_bot_username():
        if 'username' not in _bot_info_cache:
            _bot_info_cache['username'] = bot.get_me().username
        return _bot_info_cache['username']

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
        
        # Remove any persistent reply keyboard without visible clutter
        cleanup_msg = bot.send_message(message.chat.id, ".", reply_markup=ReplyKeyboardRemove(), disable_notification=True)
        try:
            bot.delete_message(message.chat.id, cleanup_msg.message_id)
        except Exception:
            pass
        
        welcome_text = (
            f"Hello {username}! 👋\n\n"
            "Welcome to the *Premium VIP Hub*.\n"
            "Get instant access to our exclusive content and community.\n\n"
            "[👇Demo👇](https://t.me/Motivational_videos_4K/4)"
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

    def _build_progress_bar(pct, length=15):
        """Build a text progress bar: ▓▓▓▓▓▓░░░░░░░░░"""
        filled = int(length * pct / 100)
        empty = length - filled
        return "▓" * filled + "░" * empty

    def _handle_profile(chat_id, user_id, username):
        import threading
        sub = get_active_subscription(user_id)
        countdown = get_subscription_with_countdown(user_id)
        
        if sub and countdown:
            plan_name = sub["plan_name"]
            end_date_str = sub["end_date"].strftime("%Y-%m-%d %H:%M:%S")
            is_active = True
            bar = _build_progress_bar(countdown["progress_pct"])
            remaining = countdown["remaining_days"]
            total = countdown["total_days"]
            msg = (
                f"✅ *Active VIP Member*\n\n"
                f"🛡️ *Current Plan:* {plan_name}\n"
                f"⏳ *Valid Until:* `{end_date_str} UTC`\n\n"
                f"📅 *Subscription Progress:*\n"
                f"`[{bar}]` {countdown['progress_pct']}%\n"
                f"📆 *{remaining} days remaining* out of {total} days"
            )
            markup = None
        elif sub:
            plan_name = sub["plan_name"]
            end_date_str = sub["end_date"].strftime("%Y-%m-%d %H:%M:%S")
            is_active = True
            msg = f"✅ *Active VIP Member*\n\n🛡️ *Current Plan:* {plan_name}\n⏳ *Valid Until:* `{end_date_str} UTC`"
            markup = None
        else:
            plan_name = "NONE"
            end_date_str = "N/A"
            is_active = False
            msg = f"👤 *Profile: {username}*\n\n❌ *Status:* Free User\n\nYou currently don't have access to the VIP channel.\nUnlock premium features by picking a plan below! 👇"
            plans = get_all_plans()
            markup = InlineKeyboardMarkup(row_width=1)
            if plans:
                for plan in plans:
                    btn_text = f"{plan['name']} ({plan['duration_days']} Days)"
                    markup.add(InlineKeyboardButton(btn_text, callback_data=f"buy_{plan['id']}"))

        # Send text response instantly, then generate card in background
        def _send_card():
            try:
                card_io = generate_vip_card(bot, user_id, username, plan_name, end_date_str, is_active)
                if card_io:
                    bot.send_photo(chat_id, photo=card_io, caption=msg, parse_mode="Markdown", reply_markup=markup)
                else:
                    send_msg_with_optional_image(bot, chat_id, profile_img, msg, parse_mode="Markdown", reply_markup=markup)
            except Exception as e:
                print(f"Error sending VIP card: {e}")
                send_msg_with_optional_image(bot, chat_id, profile_img, msg, parse_mode="Markdown", reply_markup=markup)

        threading.Thread(target=_send_card, daemon=True).start()

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
            btn_text = f"{plan['name']} ({plan['duration_days']} Days)"
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
        bot_username = _get_bot_username()
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
                
            safe_username = html_escape.escape(str(row['username']))
            safe_plan = html_escape.escape(str(row['plan_name']))
            html_content += f"""
                    <tr>
                        <td><code>{row['telegram_id']}</code></td>
                        <td>{safe_username}</td>
                        <td>{row['referrer_id']}</td>
                        <td>{row['referral_count']}</td>
                        <td>{safe_plan}</td>
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
            
        if message.text and (message.text.lower() == 'cancel' or message.text.startswith('/')):
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


    # ---------------- REVENUE CHART (#7) ---------------- #
    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_revenue")
    def callback_revenue_chart(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id, "Generating chart...")
        bot.send_message(call.message.chat.id, "⏳ Generating revenue chart...")
        chart_io = generate_revenue_chart(days=30)
        if chart_io:
            bot.send_photo(
                call.message.chat.id, photo=chart_io,
                caption="📈 *30-Day Revenue Chart*", parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
        else:
            bot.send_message(call.message.chat.id, "ℹ️ No revenue data found for the last 30 days.", reply_markup=get_admin_keyboard())

    # ---------------- PLAN MANAGER (#16) ---------------- #
    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_plans")
    def callback_plan_manager(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        _show_plan_manager(call.message.chat.id)

    def _show_plan_manager(chat_id):
        plans = get_all_plans()
        markup = InlineKeyboardMarkup(row_width=1)
        for p in plans:
            markup.add(InlineKeyboardButton(
                f"✏️ {p['name']} — ₹{p['price']} ({p['duration_days']}d)",
                callback_data=f"pedit_{p['id']}"
            ))
        markup.add(InlineKeyboardButton("➕ Add New Plan", callback_data="plan_add"))
        markup.add(InlineKeyboardButton("🔙 Back to Admin", callback_data="cmd_admin_back"))
        bot.send_message(chat_id, "📌 *Plan Manager*\n\nSelect a plan to edit or delete, or add a new one.", parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_back")
    def callback_admin_back(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "👑 *Admin Control Panel*", parse_mode="Markdown", reply_markup=get_admin_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pedit_"))
    def callback_plan_edit(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split("_")[1])
        plan = get_plan_by_id(plan_id)
        if not plan:
            bot.send_message(call.message.chat.id, "❌ Plan not found.")
            return
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"pname_{plan_id}"),
            InlineKeyboardButton("💰 Edit Price", callback_data=f"pprice_{plan_id}")
        )
        markup.add(
            InlineKeyboardButton("📅 Edit Duration", callback_data=f"pdur_{plan_id}"),
            InlineKeyboardButton("🗑️ Delete Plan", callback_data=f"pdel_{plan_id}")
        )
        markup.add(InlineKeyboardButton("🔙 Back to Plans", callback_data="cmd_admin_plans"))
        text = (
            f"📦 *Plan #{plan['id']}*\n\n"
            f"📝 *Name:* {plan['name']}\n"
            f"💰 *Price:* ₹{plan['price']}\n"
            f"📅 *Duration:* {plan['duration_days']} days"
        )
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pname_"))
    def callback_edit_plan_name(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split("_")[1])
        msg = bot.send_message(call.message.chat.id, "📝 Type the new plan name (or `cancel`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _process_plan_name_edit, plan_id)

    def _process_plan_name_edit(message, plan_id):
        if message.text and message.text.lower() == "cancel":
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_admin_keyboard())
            return
        update_plan(plan_id, name=message.text.strip())
        bot.send_message(message.chat.id, f"✅ Plan name updated to: *{message.text.strip()}*", parse_mode="Markdown")
        _show_plan_manager(message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pprice_"))
    def callback_edit_plan_price(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split("_")[1])
        msg = bot.send_message(call.message.chat.id, "💰 Enter the new price in INR (number only, or `cancel`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _process_plan_price_edit, plan_id)

    def _process_plan_price_edit(message, plan_id):
        if message.text and message.text.lower() == "cancel":
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_admin_keyboard())
            return
        try:
            price = int(message.text.strip())
            update_plan(plan_id, price=price)
            bot.send_message(message.chat.id, f"✅ Plan price updated to: *₹{price}*", parse_mode="Markdown")
            _show_plan_manager(message.chat.id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid number. Try again from Plan Manager.", reply_markup=get_admin_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pdur_"))
    def callback_edit_plan_duration(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split("_")[1])
        msg = bot.send_message(call.message.chat.id, "📅 Enter the new duration in days (number only, or `cancel`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _process_plan_dur_edit, plan_id)

    def _process_plan_dur_edit(message, plan_id):
        if message.text and message.text.lower() == "cancel":
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_admin_keyboard())
            return
        try:
            days = int(message.text.strip())
            update_plan(plan_id, duration_days=days)
            bot.send_message(message.chat.id, f"✅ Plan duration updated to: *{days} days*", parse_mode="Markdown")
            _show_plan_manager(message.chat.id)
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid number. Try again from Plan Manager.", reply_markup=get_admin_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pdel_"))
    def callback_delete_plan(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split("_")[1])
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"pdelconf_{plan_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cmd_admin_plans")
        )
        bot.send_message(call.message.chat.id, f"⚠️ *Are you sure you want to delete Plan #{plan_id}?*\n\nThis cannot be undone.", parse_mode="Markdown", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("pdelconf_"))
    def callback_confirm_delete_plan(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split("_")[1])
        if delete_plan(plan_id):
            bot.send_message(call.message.chat.id, f"🗑️ Plan #{plan_id} deleted successfully.")
        else:
            bot.send_message(call.message.chat.id, "❌ Failed to delete plan.")
        _show_plan_manager(call.message.chat.id)

    @bot.callback_query_handler(func=lambda call: call.data == "plan_add")
    def callback_add_plan(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "➕ *Add New Plan*\n\nSend plan details in this format:\n`Name | Price | Duration(days)`\n\nExample: `3 Months - ₹149 | 149 | 90`\n\nOr type `cancel`.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, _process_add_plan)

    def _process_add_plan(message):
        if message.text and message.text.lower() == "cancel":
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_admin_keyboard())
            return
        try:
            parts = [p.strip() for p in message.text.split("|")]
            name, price, days = parts[0], int(parts[1]), int(parts[2])
            new_plan = create_plan(name, price, days)
            bot.send_message(message.chat.id, f"✅ *Plan Created!*\n\n📝 {new_plan['name']}\n💰 ₹{new_plan['price']}\n📅 {new_plan['duration_days']} days", parse_mode="Markdown")
            _show_plan_manager(message.chat.id)
        except Exception:
            bot.send_message(message.chat.id, "❌ Invalid format. Use: `Name | Price | Days`", parse_mode="Markdown", reply_markup=get_admin_keyboard())

    # ---------------- SCHEDULED BROADCAST (#28) ---------------- #
    @bot.callback_query_handler(func=lambda call: call.data == "cmd_admin_schedule")
    def callback_schedule_broadcast(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        # Show existing scheduled broadcasts + option to create
        pending = get_pending_broadcasts()
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("📝 Create New Scheduled Broadcast", callback_data="sched_new"))
        for i, b in enumerate(pending[:10]):
            send_str = b["send_at"].strftime("%b %d %H:%M UTC")
            preview = (b.get("message_text") or "")[:30]
            markup.add(InlineKeyboardButton(f"❌ {send_str} — {preview}...", callback_data=f"schedcancel_{i}"))
        markup.add(InlineKeyboardButton("🔙 Back to Admin", callback_data="cmd_admin_back"))
        text = f"⏰ *Scheduled Broadcasts*\n\n📋 *Pending:* {len(pending)}\n\nTap a broadcast to cancel it, or create a new one."
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        # Store pending list for cancel reference
        bot._pending_broadcasts_cache = pending

    @bot.callback_query_handler(func=lambda call: call.data.startswith("schedcancel_"))
    def callback_cancel_scheduled(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        idx = int(call.data.split("_")[1])
        cache = getattr(bot, "_pending_broadcasts_cache", [])
        if idx < len(cache):
            bid = cache[idx]["_id"]
            if cancel_scheduled_broadcast(bid):
                bot.send_message(call.message.chat.id, "✅ Scheduled broadcast cancelled.")
            else:
                bot.send_message(call.message.chat.id, "❌ Could not cancel (may have already been sent).")
        bot.send_message(call.message.chat.id, "Return to admin:", reply_markup=get_admin_keyboard())

    @bot.callback_query_handler(func=lambda call: call.data == "sched_new")
    def callback_new_scheduled(call):
        if str(call.from_user.id) != str(admin_id): return
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "📝 *New Scheduled Broadcast*\n\n"
            "Type the message to broadcast.\n"
            "(Or type `cancel` to abort)",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, _process_sched_message)

    def _process_sched_message(message):
        if str(message.from_user.id) != str(admin_id): return
        if message.text and message.text.lower() == "cancel":
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_admin_keyboard())
            return
        broadcast_text = message.text or message.caption or ""
        media_type = None
        media_file_id = None
        if message.photo:
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
            broadcast_text = message.caption or ""
        elif message.document:
            media_type = "document"
            media_file_id = message.document.file_id
            broadcast_text = message.caption or ""

        bot._sched_draft = {"text": broadcast_text, "media_type": media_type, "media_file_id": media_file_id}
        msg = bot.send_message(
            message.chat.id,
            "⏰ *When should this be sent?*\n\n"
            "Send the date and time in this format:\n"
            "`YYYY-MM-DD HH:MM` (UTC)\n\n"
            "Example: `2026-06-05 14:30`\n\n"
            "Or type `cancel`.",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, _process_sched_time)

    def _process_sched_time(message):
        if str(message.from_user.id) != str(admin_id): return
        if message.text and message.text.lower() == "cancel":
            bot.send_message(message.chat.id, "Cancelled.", reply_markup=get_admin_keyboard())
            return
        try:
            send_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
            if send_at <= datetime.utcnow():
                bot.send_message(message.chat.id, "❌ That time is in the past. Try again.", reply_markup=get_admin_keyboard())
                return
            draft = getattr(bot, "_sched_draft", {})
            create_scheduled_broadcast(
                admin_id=message.from_user.id,
                message_text=draft.get("text", ""),
                send_at=send_at,
                media_type=draft.get("media_type"),
                media_file_id=draft.get("media_file_id")
            )
            bot.send_message(
                message.chat.id,
                f"✅ *Broadcast Scheduled!*\n\n📅 *Send at:* `{send_at.strftime('%Y-%m-%d %H:%M UTC')}`\n📝 *Message:* {draft.get('text', '')[:100]}...",
                parse_mode="Markdown", reply_markup=get_admin_keyboard()
            )
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid format. Use `YYYY-MM-DD HH:MM`", parse_mode="Markdown", reply_markup=get_admin_keyboard())

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
        if msg_text.startswith("/"):
            bot.send_message(message.chat.id, "Support request cancelled.")
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
        bot.answer_callback_query(call.id)
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

    # ---------------- RAZORPAY AUTO-VERIFIED PAYMENTS ---------------- #
    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
    def process_plan_selection(call):
        bot.answer_callback_query(call.id)
        plan_id = int(call.data.split('_')[1])
        plan = get_plan_by_id(plan_id)
        if not plan: return

        user_id = call.from_user.id
        username = call.from_user.username or call.from_user.first_name
        chat_id = call.message.chat.id

        bot.send_message(chat_id, "⏳ Generating your secure payment QR code...")

        # Run QR generation + send in a background thread
        import threading
        def _generate_and_send():
            try:
                qr_result = generate_razorpay_qr(
                    telegram_id=user_id, username=username,
                    plan_id=plan_id, plan_name=plan['name'], amount=plan['price']
                )
                if not qr_result:
                    bot.send_message(chat_id, "❌ Failed to generate payment QR. Please try again later or contact support.")
                    return

                caption = (
                    f"🛒 *Checkout: {plan['name']}*\n\n"
                    f"💸 *Amount:* `₹{plan['price']}`\n"
                    f"🔐 *QR ID:* `{qr_result['qr_id']}`\n"
                    f"⏰ *Valid for:* 30 minutes\n\n"
                    "📱 Scan the QR code with any UPI app (GPay, PhonePe, Paytm, etc.) to pay.\n\n"
                    "✅ *Your payment will be verified automatically!*\n"
                    "Once paid, you'll receive your VIP channel invite link within seconds — no screenshots needed!"
                )
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔄 Check Payment Status", callback_data=f"chkpay_{qr_result['qr_id']}"))

                # Send Razorpay QR image URL directly (no download/crop)
                try:
                    bot.send_photo(chat_id, photo=qr_result['image_url'], caption=caption, reply_markup=markup, parse_mode="Markdown")
                except Exception:
                    # Fallback: send as inline URL button
                    fallback_markup = InlineKeyboardMarkup(row_width=1)
                    fallback_markup.add(
                        InlineKeyboardButton("🔗 Open QR Code to Pay", url=qr_result['image_url']),
                        InlineKeyboardButton("🔄 Check Payment Status", callback_data=f"chkpay_{qr_result['qr_id']}")
                    )
                    bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=fallback_markup)
            except Exception as e:
                print(f"Error in QR generation thread: {e}")
                bot.send_message(chat_id, "❌ Something went wrong. Please try again.")

        threading.Thread(target=_generate_and_send, daemon=True).start()

    @bot.callback_query_handler(func=lambda call: call.data.startswith('chkpay_'))
    def check_payment_status(call):
        """Manual payment status check button for users."""
        bot.answer_callback_query(call.id, "Checking payment status...")
        qr_id = call.data.split('chkpay_')[1]

        from src.pending_payments import find_pending_by_qr_id, is_event_already_processed
        from src.razorpay_client import fetch_qr_code

        # Check if already processed
        if is_event_already_processed(qr_id):
            bot.send_message(call.message.chat.id, "✅ This payment has already been verified! Check your DMs for the invite link.")
            return

        try:
            qr_data = fetch_qr_code(qr_id)
            status = qr_data.get("status", "unknown")

            if status == "closed" and qr_data.get("payments_count_received", 0) > 0:
                # Payment received — trigger the fulfillment
                pending = find_pending_by_qr_id(qr_id)
                if pending:
                    _fulfill_payment(call.message.chat.id, pending, qr_id)
                else:
                    bot.send_message(call.message.chat.id, "✅ Payment received! Processing your subscription...")
            elif status == "active":
                bot.send_message(
                    call.message.chat.id,
                    "⏳ *Payment not yet received.*\n\nPlease scan the QR code and complete the UPI payment. Once done, click the button again to check.",
                    parse_mode="Markdown"
                )
            elif status == "expired" or status == "closed":
                bot.send_message(
                    call.message.chat.id,
                    "❌ This QR code has expired. Please use `💎 Get Premium` to generate a new one.",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(call.message.chat.id, f"ℹ️ QR Status: {status}. Please try again in a moment.")
        except Exception as e:
            print(f"Error checking QR status {qr_id}: {e}")
            bot.send_message(call.message.chat.id, "❌ Could not check status. Please try again.")

    def _fulfill_payment(chat_id, pending_doc, qr_id, razorpay_payment_id=None):
        """
        Core fulfillment logic — creates subscription, sends invite link, handles referral.
        Called by both webhook and manual status check.
        """
        from src.pending_payments import mark_payment_paid, is_event_already_processed

        # Idempotency: don't process twice
        if is_event_already_processed(qr_id):
            return

        telegram_id = pending_doc["telegram_id"]
        plan_id = pending_doc["plan_id"]

        # Mark as paid
        mark_payment_paid(qr_id, razorpay_payment_id)

        # Create subscription
        new_sub = create_subscription(telegram_id, plan_id)
        if not new_sub:
            bot.send_message(telegram_id, "❌ Error creating your subscription. Please contact support.")
            bot.send_message(admin_id, f"⚠️ Razorpay payment confirmed but subscription creation failed for user `{telegram_id}`, plan `{plan_id}`, QR `{qr_id}`")
            return

        # Generate single-use invite link
        try:
            invite_link = bot.create_chat_invite_link(chat_id=private_channel_id, member_limit=1).invite_link
            success_msg = (
                f"🎉 *Payment Verified Automatically!*\n\n"
                f"Thank you for subscribing to the *{new_sub['plan_name']}* plan.\n"
                f"Your access is valid until: `{new_sub['end_date'].strftime('%Y-%m-%d %H:%M UTC')}`\n\n"
                f"👉 [Click here to join the private channel]({invite_link})\n\n"
                f"_(This link can only be used once.)_"
            )
            bot.send_message(telegram_id, success_msg, parse_mode="Markdown", disable_web_page_preview=True)

            # Send payment receipt image
            try:
                receipt_io = generate_receipt_image(
                    username=pending_doc.get("username", "N/A"),
                    telegram_id=telegram_id,
                    plan_name=new_sub["plan_name"],
                    amount=pending_doc.get("amount", 0),
                    qr_id=qr_id,
                    payment_id=razorpay_payment_id,
                    expiry_date=new_sub["end_date"]
                )
                if receipt_io:
                    bot.send_photo(telegram_id, photo=receipt_io, caption="🧾 *Your Payment Receipt*", parse_mode="Markdown")
            except Exception as e:
                print(f"Error sending receipt: {e}")

            # Notify admin
            admin_msg = (
                f"💰 *New Razorpay Payment*\n\n"
                f"👤 *User:* {pending_doc.get('username', 'N/A')} (`{telegram_id}`)\n"
                f"📦 *Plan:* {new_sub['plan_name']}\n"
                f"💸 *Amount:* ₹{pending_doc.get('amount', '?')}\n"
                f"🔐 *QR ID:* `{qr_id}`\n"
                f"✅ *Auto-Verified & Delivered*"
            )
            try:
                bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
            except Exception:
                pass

            # Referral reward
            if new_sub.get("referrer_id"):
                rewarded = add_referral_bonus(new_sub["referrer_id"], bonus_days=7)
                if rewarded:
                    try:
                        ref_msg = "🎉 *Referral Bonus Unlocked!*\n\nSomeone just used your unique referral link to buy a subscription!\nWe have added **+7 Days** of VIP access to your account as a thank you! 📈"
                        bot.send_message(new_sub["referrer_id"], ref_msg, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Could not message referrer: {e}")

        except Exception as e:
            bot.send_message(admin_id, f"❌ Payment confirmed but invite link generation failed: {e}\nUser: `{telegram_id}`, QR: `{qr_id}`")
            bot.send_message(telegram_id, "✅ Payment received! Our admin will send your invite link shortly.")

    # Expose _fulfill_payment so webhook handler in main.py can call it
    bot._fulfill_payment = _fulfill_payment

