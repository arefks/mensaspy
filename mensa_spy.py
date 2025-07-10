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

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# Define /start or /mensa command to show mensa list
async def mensa_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Institutes Viertel", callback_data='1779')],
        [InlineKeyboardButton("Köln Sportpark Müngersdorf", callback_data='389')],
        [InlineKeyboardButton("Köln Robert-Koch-Straße", callback_data='386')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Bitte wähle eine Mensa:', reply_markup=reply_markup)

# Handle button clicks and fetch meals
async def mensa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    canteen_id = query.data
    today = datetime.date.today().isoformat()
    url = f"https://openmensa.org/api/v2/canteens/{canteen_id}/days/{today}/meals"

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

# Main bot initialization
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("mensa", mensa_list))
    app.add_handler(CallbackQueryHandler(mensa_callback))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
