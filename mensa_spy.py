import os
import datetime
import requests
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from apscheduler.schedulers.background import BackgroundScheduler

# Read secrets from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise ValueError("Please set TELEGRAM_TOKEN and CHAT_ID environment variables.")

bot = Bot(token=TELEGRAM_TOKEN)
scheduler = BackgroundScheduler()

def get_mensa_menu():
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
    return message

def send_menu(context: CallbackContext):
    try:
        message = get_mensa_menu()
        context.bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"Failed to send scheduled menu: {e}")

def menu_command(update: Update, context: CallbackContext):
    try:
        message = get_mensa_menu()
        update.message.reply_text(message)
    except Exception as e:
        update.message.reply_text(f"Failed to retrieve menu: {e}")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Add handler for /menu command
    dispatcher.add_handler(CommandHandler("menu", menu_command))

    # Schedule the daily 9 AM menu send
    scheduler.add_job(send_menu, 'cron', hour=9, minute=0, args=[updater.job_queue])
    scheduler.start()

    print("Bot started. Listening for commands and sending daily menu at 9 AM.")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
