import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # Not used directly here, but useful if needed.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send /menu to get today's Mensa menu.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today().isoformat()
    url = f"https://openmensa.org/api/v2/canteens/1839/days/{today}/meals"
    response = requests.get(url)
    if response.status_code == 200:
        meals = response.json()
        if meals:
            message = f"🍽️ Freiburg Mensa Menu for {today}:\n"
            for meal in meals:
                message += f"- {meal['category']}: {meal['name']}\n"
        else:
            message = "There are no meals listed for today. 💤"
    else:
        message = "⚠️ Error retrieving the menu."

    await update.message.reply_text(message)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
