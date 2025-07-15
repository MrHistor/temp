import logging import datetime import json import re from pathlib import Path from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember, Chat) from telegram.ext import (ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler, JobQueue)

Пути к файлам

BIRTHDAYS_FILE = Path("birthdays.json") WISHLISTS_FILE = Path("wishlists.json") SETTINGS_FILE = Path("settings.json") TOKEN_FILE = Path("token.txt")

Загрузка токена

with open(TOKEN_FILE) as f: TOKEN = f.read().strip()

Админ бота

ADMIN_USERNAME = "@mr_jasp"

Инициализация логгера

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

Загрузка данных

birthdays = json.loads(BIRTHDAYS_FILE.read_text()) if BIRTHDAYS_FILE.exists() else {} wishlists = json.loads(WISHLISTS_FILE.read_text()) if WISHLISTS_FILE.exists() else {} settings = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {"reminder_hour": 13}

--- Вспомогательные функции ---

def save_data(): BIRTHDAYS_FILE.write_text(json.dumps(birthdays, indent=2)) WISHLISTS_FILE.write_text(json.dumps(wishlists, indent=2)) SETTINGS_FILE.write_text(json.dumps(settings, indent=2))

def censor(text): banned = ["мат", "ругательство", "оскорбление"] for word in banned: text = re.sub(word, "***", text, flags=re.IGNORECASE) return text

def parse_date(text): try: return datetime.datetime.strptime(text, "%d.%m.%Y").date() except ValueError: return None

def get_username(user): return user.username and f"@{user.username}" or user.full_name

--- Обработка новых участников ---

async def greet_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE): for member in update.chat_member.new_chat_members: await context.bot.send_message(chat_id=member.id, text=""" Привет! Я бот для напоминаний о днях рождения и желаемых подарках. 🎉🎁

1. Я напомню участникам о чужих днях рождения за 2 недели и в сам день.


2. Я попрошу составить wish-лист за месяц до твоего дня рождения.


3. Ты можешь сам посмотреть и обновить свой список подарков.



Для начала отправь мне свою дату рождения в формате ДД.ММ.ГГГГ """)

--- Основные команды ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Привет! Я бот для напоминаний о днях рождения и желаемых подарках.")

async def set_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE): date = parse_date(update.message.text) if date: birthdays[str(update.message.from_user.id)] = date.isoformat() save_data() await update.message.reply_text(f"Дата рождения сохранена: {date.strftime('%d.%m.%Y')}") else: await update.message.reply_text("Неверный формат. Введите в формате ДД.ММ.ГГГГ")

async def my_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE): uid = str(update.message.from_user.id) keyboard = [[InlineKeyboardButton("Добавить", callback_data="add")], [InlineKeyboardButton("Обновить", callback_data="update")], [InlineKeyboardButton("Удалить", callback_data="delete")]] if uid in wishlists: items = wishlists[uid] text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)]) await update.message.reply_text("Твой wish-лист:\n" + text, reply_markup=InlineKeyboardMarkup(keyboard)) else: await update.message.reply_text("У тебя пока нет wish-листа. Напиши первую позицию, и я начну его.") context.user_data["waiting_for_wish"] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE): uid = str(update.message.from_user.id) text = censor(update.message.text.strip())

if context.user_data.get("waiting_for_wish"):
    context.user_data.pop("waiting_for_wish")
    wishlists.setdefault(uid, []).append(text)
    save_data()
    await update.message.reply_text("Добавлено в твой wish-лист. Хочешь добавить ещё? Напиши новую позицию или /done")
    context.user_data["waiting_for_wish"] = True
elif context.user_data.get("update_index") is not None:
    idx = context.user_data.pop("update_index")
    if uid in wishlists and 0 <= idx < len(wishlists[uid]):
        wishlists[uid][idx] = text
        save_data()
        await update.message.reply_text("Позиция обновлена.")
else:
    date = parse_date(text)
    if date:
        await set_birthday(update, context)
    else:
        await update.message.reply_text("Не понял. Используй команды или напиши /start")

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE): context.user_data.pop("waiting_for_wish", None) await update.message.reply_text("Окей, закончили с wish-листом. 😊")

async def wishlist_button(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() uid = str(query.from_user.id) data = query.data

if data == "add":
    context.user_data["waiting_for_wish"] = True
    await query.message.reply_text("Напиши новую позицию для wish-листа.")

elif data == "update":
    if uid in wishlists:
        keyboard = [[InlineKeyboardButton(f"{i+1}. {item[:20]}", callback_data=f"edit_{i}")]
                    for i, item in enumerate(wishlists[uid])]
        await query.message.reply_text("Выбери позицию для редактирования:",
                                       reply_markup=InlineKeyboardMarkup(keyboard))

elif data == "delete":
    if uid in wishlists:
        wishlists.pop(uid)
        save_data()
        await query.message.reply_text("Wish-лист удалён.")

elif data.startswith("edit_"):
    idx = int(data.split("_")[1])
    context.user_data["update_index"] = idx
    await query.message.reply_text("Напиши новую формулировку для этой позиции:")

--- Админ-команды ---

async def admin_add_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.message.from_user.username != ADMIN_USERNAME[1:]: await update.message.reply_text("Недостаточно прав.") return if len(context.args) != 2: await update.message.reply_text("Используй: /add_birthday <user_id> <дд.мм.гггг>") return user_id, date_str = context.args date = parse_date(date_str) if date: birthdays[str(user_id)] = date.isoformat() save_data() await update.message.reply_text("Дата добавлена.") else: await update.message.reply_text("Неверный формат даты")

async def admin_set_hour(update: Update, context: ContextTypes.DEFAULT_TYPE): if update.message.from_user.username != ADMIN_USERNAME[1:]: await update.message.reply_text("Недостаточно прав.") return if len(context.args) != 1 or not context.args[0].isdigit(): await update.message.reply_text("Используй: /set_hour <час>") return settings["reminder_hour"] = int(context.args[0]) save_data() await update.message.reply_text(f"Время напоминаний изменено на {context.args[0]}:00")

async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE): text = "Список дней рождения:\n" keyboard = [] for uid, iso in birthdays.items(): try: user = await context.bot.get_chat(uid) name = get_username(user) bday = datetime.date.fromisoformat(iso).strftime('%d.%m') text += f"{name}: {bday}\n" if uid in wishlists: keyboard.append([InlineKeyboardButton(f"Wish-лист {name}", callback_data=f"showwl_{uid}")]) except: continue await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_other_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE): query = update.callback_query await query.answer() uid = query.data.split("_")[1] if uid in wishlists: items = wishlists[uid] text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)]) await query.message.reply_text(f"Wish-лист пользователя:\n{text}") else: await query.message.reply_text("Wish-лист не найден.")

async def next_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE): today = datetime.date.today() upcoming = [] for uid, iso in birthdays.items(): try: bday = datetime.date.fromisoformat(iso) this_year = bday.replace(year=today.year) if this_year < today: this_year = this_year.replace(year=today.year + 1) upcoming.append((this_year, uid)) except: continue upcoming.sort() text = "Ближайшие дни рождения:\n" for d, uid in upcoming[:5]: try: user = await context.bot.get_chat(uid) name = get_username(user) text += f"{name} — {d.strftime('%d.%m')}\n" except: continue await update.message.reply_text(text)

--- Напоминания ---

def schedule_jobs(application): job_queue = application.job_queue job_queue.run_daily(send_reminders, time=datetime.time(settings["reminder_hour"]))

async def send_reminders(context: ContextTypes.DEFAULT_TYPE): today = datetime.date.today() for uid, iso_date in birthdays.items(): bday = datetime.date.fromisoformat(iso_date) next_bday = bday.replace(year=today.year) if next_bday < today: next_bday = next_bday.replace(year=today.year + 1)

delta = (next_bday - today).days
    if delta in [0, 14]:
        text = f"🎉 Скоро день рождения {get_username(await context.bot.get_chat(uid))} ({next_bday.strftime('%d.%m')})!"
        for user_id in birthdays:
            if user_id != uid:
                try:
                    await context.bot.send_message(chat_id=user_id, text=text)
                except:
                    continue

    if delta == 30:
        try:
            await context.bot.send_message(chat_id=uid, text="Через месяц у тебя день рождения! Хочешь составить или обновить wish-лист? Напиши первую позицию!")
            context.user_data["waiting_for_wish"] = True
        except:
            continue

--- Запуск ---

if name == 'main': app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("my_wishlist", my_wishlist))
app.add_handler(CommandHandler("done", done))
app.add_handler(CommandHandler("add_birthday", admin_add_birthday))
app.add_handler(CommandHandler("set_hour", admin_set_hour))
app.add_handler(CommandHandler("birthdays", list_birthdays))
app.add_handler(CommandHandler("next_birthdays", next_birthdays))
app.add_handler(CallbackQueryHandler(wishlist_button, pattern="^(add|update|delete|edit_\\d+)$"))
app.add_handler(CallbackQueryHandler(show_other_wishlist, pattern="^showwl_\\d+$"))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_new_member))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))

schedule_jobs(app)
app.run_polling()
