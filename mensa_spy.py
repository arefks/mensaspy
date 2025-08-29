# findmensabot.py

import os
import datetime
import requests
import asyncio
from uuid import uuid4
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    InlineQueryHandler, ContextTypes
)
from dotenv import load_dotenv
import nest_asyncio
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import time as dtime

# ---------- Timezone ----------
BERLIN_TZ = ZoneInfo("Europe/Berlin")
def berlin_today():
    return datetime.datetime.now(BERLIN_TZ).date()

# Load token from .env
dotenv_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path)
TOKEN = os.getenv("TELEGRAM_TOKEN")

# --------- Global State ---------
user_recent_canteens = {}  # user_id -> list of (name, id)
user_last_date = {}        # user_id -> last viewed date per user
user_reminders = {}        # user_id -> canteen_id

# Logging state
unique_users = set()
total_interactions = 0

# --------- Logging Helper ---------
def log_usage(update: Update):
    global total_interactions
    user_id = update.effective_user.id if update.effective_user else None
    username = update.effective_user.username if update.effective_user else None
    if user_id:
        unique_users.add(user_id)
    total_interactions += 1
    print(f"📊 Stats: {len(unique_users)} unique users, {total_interactions} total interactions | Latest: {username} ({user_id})")


# --------- Fetch All Canteens ---------
def fetch_canteens():
    print("📡 Fetching all canteens from OpenMensa...")
    canteens = []
    page = 1
    while True:
        url = f"https://openmensa.org/api/v2/canteens?page={page}"
        response = requests.get(url)
        data = response.json()
        if not data:
            break
        canteens.extend(data)
        page += 1
    print(f"✅ Fetched {len(canteens)} canteens.")
    return canteens

all_canteens = fetch_canteens()
all_cities = sorted(set(c['city'] for c in all_canteens if c.get('city')))

# --------- /start ---------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_usage(update)
    user_id = update.effective_user.id
    recent = user_recent_canteens.get(user_id, [])

    help_text = (
        "👋 Welcome to FindMensa Bot!\n\n"
        "ℹ️ How to use this bot:\n\n"
        "1. After starting the bot, type:\n"
        "`@mensaspybot in the chat and add yourcity`\n\n"
        "2. Select your city from the list.\n"
        "3. Choose a canteen to view today’s meals.\n"
        "4. Use the ➡️ 'Next Day' button to see meals for the next day.\n"
        "5. Use `/remind <canteen_id>` to get daily notifications at 9:30am (Mon–Fri).\n"
        "   Use `/remind` without ID to turn it off."
    )

    await update.message.reply_text(help_text, parse_mode="Markdown")

    if recent:
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"canteen_{cid}")]
            for name, cid in recent
        ]
        await update.message.reply_text("🕘 Recently viewed canteens:", reply_markup=InlineKeyboardMarkup(keyboard))

# --------- /help ---------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_usage(update)
    await start(update, context)

# --------- Inline Search ---------
async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_usage(update)
    query = update.inline_query.query.lower()
    results = []

    if not query:
        # If the query is empty, return first 50 alphabetically sorted cities
        matching = all_cities[:50]
    else:
        # Show cities containing the query
        matching = [c for c in all_cities if query in c.lower()][:50]

    for city in matching:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title=city,
                input_message_content=InputTextMessageContent(f"/searchcity {city}"),
                description="Show canteens in this city"
            )
        )

    await update.inline_query.answer(results, cache_time=1)


# --------- /searchcity [City] ---------
async def searchcity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_usage(update)
    if not context.args:
        await update.message.reply_text("❌ Please provide a city name. Example: /searchcity Berlin")
        return

    city = " ".join(context.args).strip().lower()
    matches = [c for c in all_canteens if c.get("city", "").lower() == city]

    if not matches:
        await update.message.reply_text(f"❌ No canteens found in '{city.title()}'.")
        return

    keyboard = [
        [InlineKeyboardButton(c["name"], callback_data=f"canteen_{c['id']}")]
        for c in matches
    ]

    await update.message.reply_text(f"🍽 Canteens in {city.title()}:", reply_markup=InlineKeyboardMarkup(keyboard))

# --------- Reminders (Europe/Berlin @ 09:30 Mon–Fri) ---------
async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    # Runs at 09:30 Europe/Berlin by job queue
    data = context.job.data or {}
    user_id = data.get("user_id")
    canteen_id = data.get("canteen_id")
    if not user_id or not canteen_id:
        return
    await send_meals_direct(context.application, user_id, canteen_id, date=berlin_today())

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_usage(update)
    user_id = update.effective_user.id

    # Helper: cancel existing job(s) for this user
    def cancel_existing_jobs():
        jobs = context.job_queue.get_jobs_by_name(f"remind_{user_id}")
        for j in jobs:
            j.schedule_removal()

    if not context.args:
        user_reminders.pop(user_id, None)
        cancel_existing_jobs()
        await update.message.reply_text("🔕 Reminder disabled.")
        return

    try:
        canteen_id = int(context.args[0])
        canteen = next(c for c in all_canteens if c['id'] == canteen_id)

        # Save chosen canteen
        user_reminders[user_id] = canteen_id

        # Cancel previous job (if any) and schedule a new one in Berlin time
        cancel_existing_jobs()
        context.job_queue.run_daily(
            reminder_job,
            time=dtime(hour=9, minute=30, tzinfo=BERLIN_TZ),
            days=(0, 1, 2, 3, 4),  # Mon–Fri
            name=f"remind_{user_id}",
            data={"user_id": user_id, "canteen_id": canteen_id},
        )

        await update.message.reply_text(
            f"⏰ Daily reminder set for {canteen['name']} ({canteen['city']}) at 9:30am (Mon–Fri, Europe/Berlin)."
        )
    except:
        await update.message.reply_text("❌ Invalid canteen ID.")

# --------- Handle Canteen Clicks ---------
async def canteen_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_usage(update)
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    data = query.data
    if data.startswith("canteen_"):
        canteen_id = int(data.split("_")[1])
        user_last_date[user_id] = berlin_today()
        await send_meals(query, canteen_id, user_id)

    elif data.startswith("nextday_"):
        canteen_id = int(data.split("_")[1])
        current = user_last_date.get(user_id, berlin_today())
        next_day = current + datetime.timedelta(days=1)
        user_last_date[user_id] = next_day
        await send_meals(query, canteen_id, user_id, date=next_day)

# --------- Send Meals (reply to a message) ---------
async def send_meals(query, canteen_id, user_id, date=None):
    if date is None:
        date = berlin_today()

    url = f"https://openmensa.org/api/v2/canteens/{canteen_id}/days/{date.isoformat()}/meals"
    name = next((c['name'] for c in all_canteens if c['id'] == canteen_id), f"Mensa {canteen_id}")
    city = next((c['city'] for c in all_canteens if c['id'] == canteen_id), "Unknown")

    try:
        response = requests.get(url)
        response.raise_for_status()
        meals = response.json()

        if meals:
            meal_texts = [
                f"{meal['category']}: {meal['name']} ({meal['prices']['students']}€)"
                for meal in meals
            ]
            text = f"🍽 {name} (ID: {canteen_id}, {city}) — {date}\n\n" + "\n".join(meal_texts)
        else:
            text = f"🍽 {name} (ID: {canteen_id}, {city}) — {date}\nNo meals available today."

    except Exception as e:
        text = (
            f"🍽 {name} — {date}\n\n"
            "⚠️ Error fetching meals.\n\n"
            "😐 Something went wrong, 😐!\n"
            "Either this canteen is closed today 😐, forgot to cook 😐, or the bot has a personal problem with you 😏.\n"
            "Try again tomorrow or pick another one!\n\n"
            "💨"
        )

    # Save to recent
    recent = user_recent_canteens.get(user_id, [])
    entry = (name, canteen_id)
    if entry in recent:
        recent.remove(entry)
    recent.insert(0, entry)
    user_recent_canteens[user_id] = recent[:5]

    keyboard = [[InlineKeyboardButton("➡️ Next Day", callback_data=f"nextday_{canteen_id}")]]
    await query.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))

# --------- Send Meals (direct message, used by reminders) ---------
async def send_meals_direct(application, chat_id, canteen_id, date=None):
    if date is None:
        date = berlin_today()

    url = f"https://openmensa.org/api/v2/canteens/{canteen_id}/days/{date.isoformat()}/meals"
    name = next((c['name'] for c in all_canteens if c['id'] == canteen_id), f"Mensa {canteen_id}")
    city = next((c['city'] for c in all_canteens if c['id'] == canteen_id), "Unknown")

    try:
        response = requests.get(url)
        response.raise_for_status()
        meals = response.json()

        if meals:
            meal_texts = [
                f"{meal['category']}: {meal['name']} ({meal['prices']['students']}€)"
                for meal in meals
            ]
            text = f"⏰ Daily reminder\n\n🍽 {name} (ID: {canteen_id}, {city}) — {date}\n\n" + "\n".join(meal_texts)
        else:
            text = f"⏰ Daily reminder\n\n🍽 {name} (ID: {canteen_id}, {city}) — {date}\nNo meals available today."

    except Exception:
        text = (
            f"⏰ Daily reminder\n\n🍽 {name} — {date}\n\n"
            "⚠️ Error fetching meals. Try again later or pick another canteen."
        )

    keyboard = [[InlineKeyboardButton("➡️ Next Day", callback_data=f"nextday_{canteen_id}")]]
    await application.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

# --------- Run Bot ---------
async def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("searchcity", searchcity_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CallbackQueryHandler(canteen_callback))
    app.add_handler(InlineQueryHandler(inline_search))

    print("🚀 findmensabot is running (Europe/Berlin timers enabled)...")
    await app.run_polling()

# --------- Entry Point ---------
def main():
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    loop.run_forever()

if __name__ == "__main__":
    main()
