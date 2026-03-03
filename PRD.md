# Product Requirements Document (PRD)
**Product Name:** VIP Premium Subscription Telegram Bot
**Date:** March 2, 2026

## 1. Product Overview
The VIP Premium Subscription Bot is an automated Telegram-based system designed to monetize exclusive content channels. It handles the entire sales funnel directly within Telegram: showcasing subscription tiers, generating dynamic UPI QR codes for frictionless payments, managing user verification, and granting/revoking access to private Telegram channels. 

The bot significantly reduces admin overhead by automating subscription tracking, enforcing expiry deadlines, parsing referral rewards, and standardizing customer support queries.

## 2. Target Audience
- **Primary Users:** Telegram users who want to purchase premium access to exclusive content, signals, or community groups.
- **Administrators:** Content creators, community managers, or business owners looking for an automated way to monetize their Telegram channels using Indian UPI architecture.

## 3. Core Features 

### 3.1 User-Facing Features 
- **Modern Inline UI:** Fully responsive floating inline keyboards for all navigation (Premium, Profile, Support, Referrals).
- **Dynamic Welcome & Media:** Automatic image attachments to greetings, help menus, and plan showcases based on environment configuration.
- **Automated Checkout via UPI:** Real-time generation of custom UPI QR Codes containing the exact plan price and a localized Transaction Reference ID.
- **Subscription Management:** Users can instantly view their active plan name, status, and precise UTC expiry date.
- **Affiliate (Referral) System:** 
  - Users receive a unique `/start ref_ID` link.
  - An inline "Share" button directly connects to Telegram's native contact-sharing overlay.
  - Referrers automatically receive **+7 Days** of VIP access when their referred user successfully completes a purchase.
- **Direct Support Desk:** Users can send support queries inside the bot, which are instantly routed to the administrator.

### 3.2 Administrator Features
- **Hidden Dashboard:** A secure, ID-locked control panel accessible only to the configured `ADMIN_ID`.
- **Screenshot Verification Flow:** Admins receive uploaded payment proofs alongside expected amounts, reference IDs, and user profiles. Approvals automatically generate single-use invite links.
- **Real-Time Analytics Dashboard:**
  - Total Registered Users
  - Total Active VIP Subscriptions
  - Estimated Current Revenue (MRR based on active plans)
- **HTML Data Export:** 1-click generation of a styled HTML report containing the complete User Database (IDs, referrers, statuses) directly sent to the admin's DMs.
- **Global Broadcasting:** Capability to blast rich-media announcements (Text, Photo, Document overlays) to the entire registered user base simultaneously.
- **Live Support Routing:** Admins receive user tickets and can reply directly to specific users using inline reply mechanisms.

### 3.3 System Automation
- **Scheduled Expiry Warnings:** Background chron-job (running at 10:00 UTC) alerting users whose VIP access expires in exactly 3 days or 24 hours.
- **Automated Kicks:** Background chron-job (running at 00:00 UTC) that scrubs the database for expired subscriptions, revokes their "Active" status, and permanently kicks them from the linked Private Telegram Channel.

## 4. Technical Architecture
### 4.1 Tech Stack
- **Language:** Python 3.10+
- **Core Library:** `pyTelegramBotAPI` (Telebot)
- **Database:** SQLite with `SQLAlchemy` ORM
- **Web Server:** `Flask` (for Webhook handling) & `gunicorn`
- **Background Tasks:** `schedule` library running on threaded daemon workers.
- **Image Generation:** `qrcode` and `Pillow` (PIL) for dynamic UPI QR construction.

### 4.2 Deployment Environment
- Designed to be deployed on serverless container platforms (e.g., Koyeb, Heroku).
- Webhook endpoints securely route Telegram API updates to the Flask application.
- Environment variables (`.env`) strictly dictate tokens, admin IDs, and styling (URLs).

### 4.3 Database Schema (Key Entities)
- **User:** `id`, `telegram_id` (Unique), `username`, `referrer_id`, `referral_count`
- **Plan:** `id`, `name`, `price`, `duration_days`
- **Subscription:** `id`, `user_id` (FK), `plan_id` (FK), `start_date`, `end_date`, `is_active`

## 5. Security Protocols
- **Strict ID Locking:** All `/admin` components and webhook registration callbacks explicitly verify the invoker's standard Telegram ID against the system `.env` configuration.
- **Single-Use Invites:** Approved payments generate API-issued Telegram `ChatInviteLink` tokens with `member_limit=1` to prevent unauthorized link sharing.
- **SQL Injection Prevention:** Utilization of strict SQLAlchemy parameterized ORM models for all dynamic data parsing.

## 6. Future Expansion Roadmap
- Promo Code System for percentage/flat discounts during seasonal events.
- Wallet top-up architecture for instant 1-click renewals via internally held balances.
- Auto-responder "Smart FAQ" inline menus to intercept tier-1 generic support queries.
- Automated API fulfillment for instant delivery of digital products (PDFs/Videos) alongside standard channel join links.
