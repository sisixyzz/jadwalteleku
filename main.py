import os
import pandas as pd
import schedule
import time
import random
import datetime
import json
from collections import defaultdict
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=TOKEN)

PROJECT_FILE = 'projects.csv'
HISTORY_FILE = 'history.csv'
WEEKLY_HISTORY_FILE = 'weekly_history.csv'
WEEKLY_SCHEDULE_FILE = 'weekly_schedule.json'

REPEAT_PER_WEEK = 4


def load_projects():
    try:
        return pd.read_csv(PROJECT_FILE)
    except:
        return pd.DataFrame(columns=["Nama Project", "Type", "Link"])


def save_projects(df):
    df.to_csv(PROJECT_FILE, index=False)


def generate_weekly_schedule():
    projects = load_projects()
    schedule_data = defaultdict(list)

    for _, row in projects.iterrows():
        assigned_days = []
        for _ in range(REPEAT_PER_WEEK):
            while True:
                day = random.randint(0, 6)
                if assigned_days.count(day) < 1:
                    assigned_days.append(day)
                    break
            schedule_data[day].append(row.to_dict())

    with open(WEEKLY_SCHEDULE_FILE, 'w') as f:
        json.dump(schedule_data, f)

    today = datetime.datetime.now()
    save_weekly_history(
        week_number=today.isocalendar()[1],
        start_date=(today - datetime.timedelta(days=today.weekday())).strftime('%d-%m-%Y'),
        end_date=(today + datetime.timedelta(days=6 - today.weekday())).strftime('%d-%m-%Y'),
        total_projects=len(projects)
    )

    bot.send_message(chat_id=CHAT_ID, text=f"🔄 Minggu baru dimulai! Total project: {len(projects)}")


def save_weekly_history(week_number, start_date, end_date, total_projects):
    history = []
    if os.path.exists(WEEKLY_HISTORY_FILE):
        history = pd.read_csv(WEEKLY_HISTORY_FILE).values.tolist()
    history.append([week_number, start_date, end_date, total_projects])
    pd.DataFrame(history, columns=["Minggu Ke-", "Tanggal Awal", "Tanggal Akhir", "Jumlah Project Total"]).to_csv(WEEKLY_HISTORY_FILE, index=False)


def send_daily_schedule():
    today = datetime.datetime.now()
    weekday = today.weekday()
    date_str = today.strftime('%d-%m-%Y')
    day_name = today.strftime('%A')

    if not os.path.exists(WEEKLY_SCHEDULE_FILE):
        generate_weekly_schedule()

    with open(WEEKLY_SCHEDULE_FILE) as f:
        weekly_schedule = json.load(f)

    daily_projects = weekly_schedule.get(str(weekday), [])

    if not daily_projects:
        bot.send_message(chat_id=CHAT_ID, text=f"📅 {day_name} ({date_str}): Tidak ada project hari ini.")
        return

    message = f"📅 Jadwal {day_name} ({date_str}):\n"
    history = []
    for p in daily_projects:
        message += f"- {p['Nama Project']} [{p['Type']}] → {p['Link']}\n"
        history.append([date_str, day_name, p['Nama Project'], p['Type']])

    pd.DataFrame(history, columns=["Tanggal", "Hari", "Project", "Type"]).to_csv(HISTORY_FILE, mode='a', header=not os.path.exists(HISTORY_FILE), index=False)

    bot.send_message(chat_id=CHAT_ID, text=message)


def add_project_csv(update: Update, context: CallbackContext):
    file = update.message.document.get_file()
    file.download("temp_projects.csv")  # simpan sementara

    # Load data lama & baru
    old_projects = load_projects()
    new_projects = pd.read_csv("temp_projects.csv")

    # Gabung data
    combined = pd.concat([old_projects, new_projects]).drop_duplicates().reset_index(drop=True)

    # Simpan ke projects.csv
    save_projects(combined)

    os.remove("temp_projects.csv")  # hapus file sementara
    update.message.reply_text("✅ CSV berhasil ditambahkan dan duplikat dihapus!")



def hapuss(update: Update, context: CallbackContext):
    with open(WEEKLY_SCHEDULE_FILE, 'w') as f:
        json.dump({}, f)
    update.message.reply_text("🗑️ Jadwal mingguan berhasil dihapus!")



def download_projects(update: Update, context: CallbackContext):
    if os.path.exists(PROJECT_FILE):
        update.message.reply_document(open(PROJECT_FILE, 'rb'))
    else:
        update.message.reply_text("⚠️ Belum ada data project.")


def download_history(update: Update, context: CallbackContext):
    if os.path.exists(HISTORY_FILE):
        update.message.reply_document(open(HISTORY_FILE, 'rb'))
    else:
        update.message.reply_text("⚠️ Belum ada history.")


def download_weekly_history(update: Update, context: CallbackContext):
    if os.path.exists(WEEKLY_HISTORY_FILE):
        update.message.reply_document(open(WEEKLY_HISTORY_FILE, 'rb'))
    else:
        update.message.reply_text("⚠️ Belum ada history mingguan.")


def start(update: Update, context: CallbackContext):
    update.message.reply_text("👋 Bot Jadwal Airdrop aktif!")


def setup_bot():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("download_projects", download_projects))
    dp.add_handler(CommandHandler("download_history", download_history))
    dp.add_handler(CommandHandler("download_weekly_history", download_weekly_history))
    dp.add_handler(MessageHandler(Filters.document.mime_type("text/csv"), add_project_csv))
    dp.add_handler(CommandHandler("hapuss", hapuss))


    updater.start_polling()
    return updater


def main():
    generate_weekly_schedule()
    schedule.every().monday.at("00:00").do(generate_weekly_schedule)
    schedule.every().day.at("04:00").do(send_daily_schedule)

    updater = setup_bot()

    print("✅ Bot berjalan...")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
