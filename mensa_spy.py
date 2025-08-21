import os
import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# --- Load Telegram Bot Token ---
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# --- /start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Received /start command")
    await update.message.reply_text("✅ Bot is working. Use /mensa to see Mensa options.")

# --- /mensa command ---
async def mensa_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Received /mensa command")
    keyboard = [
        [InlineKeyboardButton("Institutes Viertel", callback_data='1779')],
        [InlineKeyboardButton("Köln Sportpark Müngersdorf", callback_data='389')],
        [InlineKeyboardButton("Köln Robert-Koch-Straße", callback_data='386')],
        [InlineKeyboardButton("Regensburg UNI", callback_data='194')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Bitte wähle eine Mensa:', reply_markup=reply_markup)

# --- Mensa selection handler ---
async def mensa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    canteen_id = query.data
    today = datetime.date.today().isoformat()
    url = f"https://openmensa.org/api/v2/canteens/{canteen_id}/days/{today}/meals"

    print(f"Fetching meals for Mensa ID {canteen_id} on {today}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        meals = response.json()

        if meals:
            meal_texts = [
                f"{meal['category']}: {meal['name']} ({meal['prices']['students']}€)"
                for meal in meals
            ]
            text = "\n".join(meal_texts)
        else:
            text = "Heute keine Speisen verfügbar."

    except Exception as e:
        text = f"Fehler beim Abrufen des Mensaplans.\n{e}"

    await query.edit_message_text(text=text)

# --- Initialize bot ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mensa", mensa_list))
    app.add_handler(CallbackQueryHandler(mensa_callback))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
