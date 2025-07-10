import requests
from telegram import Bot
from apscheduler.schedulers.blocking import BlockingScheduler
import datetime
import os

# Replace with your actual bot token and chat ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "your_bot_token_here")
CHAT_ID = os.getenv("CHAT_ID", "your_chat_id_here")

bot = Bot(token=TELEGRAM_TOKEN)
scheduler = BlockingScheduler()

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

    bot.send_message(chat_id=CHAT_ID, text=message)

# Schedule the job at 9:00 AM every day
scheduler.add_job(get_mensa_menu, 'cron', hour=9, minute=0)
print("Bot is running. It will send the menu every day at 9:00 AM.")
scheduler.start()
