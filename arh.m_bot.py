import json import logging import datetime import os 
from pathlib import Path from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton) 
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackContext)

Enable logging

token_file = Path('token.txt') if not token_file.exists(): raise RuntimeError('token.txt not found') TOKEN = token_file.read_text().strip()

logging.basicConfig( format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO ) logger = logging.getLogger(name)

BIRTH_FILE = Path('birthdays.json') WISH_FILE = Path('wishlists.json') ADMIN_USERNAME = 'mr_jasp'

Load or initialize data

def load_data(path, default): if path.exists(): return json.loads(path.read_text()) else: return default

def save_data(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

birthdays = load_data(BIRTH_FILE, {})  # user_id -> 'YYYY-MM-DD' wishlists = load_data(WISH_FILE, {})  # user_id -> list[str]

Conversation states

ASK_DOB, ASK_WISH = range(2) UPDATE_CHOICE, UPDATE_INDEX, NEW_WISH = range(2, 5)

Helper functions

def validate_date(date_text): try: datetime.datetime.strptime(date_text, '%Y-%m-%d') return True except ValueError: return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): user = update.effective_user if update.message.chat.type in ['group', 'supergroup']: await update.message.reply_text( f"Привет, я бот напоминаний о днях рождения и wish-листах." "Добавьте меня в группу, и я напомню всем участникам о грядущих днях рождениях." ) else: await update.message.reply_text("Используйте этого бота в группе.")

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE): for member in update.message.new_chat_members: if member.is_bot: continue await update.message.reply_text( f"Добро пожаловать, {member.full_name}! 👋\n" + "Пожалуйста, отправьте дату вашего рождения в формате YYYY-MM-DD.") return ASK_DOB return ConversationHandler.END

async def ask_dob(update: Update, context: ContextTypes.DEFAULT_TYPE): user = update.effective_user text = update.message.text.strip() if not validate_date(text): await update.message.reply_text("Неверный формат даты. Попробуйте снова (YYYY-MM-DD):") return ASK_DOB birthdays[str(user.id)] = text save_data(BIRTH_FILE, birthdays) context.user_data['dob'] = text await update.message.reply_text( "Отлично! Теперь создадим ваш wish-лист. Отправьте первую позицию:") wishlists[str(user.id)] = [] save_data(WISH_FILE, wishlists) return ASK_WISH

async def ask_wish(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = str(update.effective_user.id) text = update.message.text.strip() if text: wishlists[user_id].append(text) save_data(WISH_FILE, wishlists) await update.message.reply_text("Позиция добавлена. Если хотите добавить еще, отправьте новую позицию, иначе /done.") return ASK_WISH

async def done_wish(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Ваш wish-лист создан! Спасибо.") return ConversationHandler.END

User commands

async def show_wish(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = str(update.effective_user.id) wl = wishlists.get(user_id) if not wl: return await update.message.reply_text("У вас еще нет wish-листа. Используйте /update_wish, чтобы создать его.") text = "Ваш wish-лист:\n" + "\n".join(f"{i+1}. {item}" for i, item in enumerate(wl)) await update.message.reply_text(text)

async def delete_wish(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = str(update.effective_user.id) if user_id in wishlists: del wishlists[user_id] save_data(WISH_FILE, wishlists) await update.message.reply_text("Ваш wish-лист удален.") else: await update.message.reply_text("У вас нет wish-листа.")

async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE): if not birthdays: return await update.message.reply_text("Нет сохраненных дней рождения.") text = "Дни рождения участников:\n" for uid, dob in birthdays.items(): user = await context.bot.get_chat(int(uid)) text += f"{user.full_name}: {dob}\n" await update.message.reply_text(text)

async def list_birthdays_with_wish(update: Update, context: ContextTypes.DEFAULT_TYPE): if not birthdays: return await update.message.reply_text("Нет сохраненных данных.") msg = [] for uid, dob in birthdays.items(): user = await context.bot.get_chat(int(uid)) msg.append(f"{user.full_name}: {dob}") wl = wishlists.get(uid) if wl: msg.extend(f"  {i+1}. {item}" for i, item in enumerate(wl)) await update.message.reply_text("\n".join(msg))

Update wish list

async def update_wish_command(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = str(update.effective_user.id) wl = wishlists.get(user_id, []) if not wl: await update.message.reply_text("У вас нет wish-листа. Отправьте /update_wish, чтобы создать.") return ConversationHandler.END keyboard = [[str(i+1)] for i in range(len(wl))] + [['add'], ['cancel']] await update.message.reply_text( "Выберите номер позиции для обновления или 'add' для добавления новой:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True) ) return UPDATE_CHOICE

async def update_choice(update: Update, context: ContextTypes.DEFAULT_TYPE): text = update.message.text.strip() user_id = str(update.effective_user.id) wl = wishlists.get(user_id, []) if text == 'add': await update.message.reply_text("Отправьте новую позицию:") context.user_data['action'] = 'add' return NEW_WISH if text.isdigit() and 1 <= int(text) <= len(wl): index = int(text) - 1 context.user_data['index'] = index await update.message.reply_text("Отправьте новый текст для выбранной позиции:") context.user_data['action'] = 'update' return NEW_WISH await update.message.reply_text("Неверный выбор, попробуйте снова или /cancel.") return UPDATE_CHOICE

async def process_new_wish(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = str(update.effective_user.id) text = update.message.text.strip() action = context.user_data.get('action') if action == 'add': wishlists[user_id].append(text) elif action == 'update': idx = context.user_data['index'] wishlists[user_id][idx] = text save_data(WISH_FILE, wishlists) await update.message.reply_text("Ваш wish-лист обновлен.") return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE): await update.message.reply_text("Операция отменена.") return ConversationHandler.END

Admin commands

def admin_only(func): async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs): if update.effective_user.username != ADMIN_USERNAME: return await update.message.reply_text("Только администратор может это делать.") return await func(update, context, *args, **kwargs) return wrapper

@admin_only async def add_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE): parts = update.message.text.split() if len(parts) != 3 or not validate_date(parts[2]): return await update.message.reply_text("Использование: /add_birthday @username YYYY-MM-DD") username, date = parts[1], parts[2] try: user = await context.bot.get_chat(username) except: return await update.message.reply_text("Пользователь не найден.") birthdays[str(user.id)] = date save_data(BIRTH_FILE, birthdays) await update.message.reply_text(f"Добавлен день рождения: {user.full_name} - {date}")

@admin_only async def set_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE): parts = update.message.text.split() if len(parts) != 2: return await update.message.reply_text("Использование: /set_time HH:MM") try: h, m = map(int, parts[1].split(':')) context.job_queue.run_daily(reminder_job, time=datetime.time(hour=h, minute=m), context=update.message.chat_id) await update.message.reply_text(f"Время напоминаний установлено на {parts[1]}") except ValueError: await update.message.reply_text("Неверный формат времени.")

Reminder job

def get_today(): return datetime.date.today()

async def reminder_job(context: ContextTypes.DEFAULT_TYPE): chat_id = context.job.chat_id today = get_today() for uid, dob in birthdays.items(): date = datetime.datetime.strptime(dob, '%Y-%m-%d').date() delta = (date.replace(year=today.year) - today).days if delta == 0 or delta == 14: user = await context.bot.get_chat(int(uid)) when = 'сегодня' if delta == 0 else f'через 2 недели ({dob})' await context.bot.send_message( chat_id=chat_id, text=f"Напоминание: у {user.full_name} день рождения {when}. " f"@{user.username if user.username else ''}" ) if delta == 30: await context.bot.send_message( chat_id=int(uid), text=f"Ваш день рождения через месяц ({dob}). Пожалуйста, обновите или создайте wish-лист." "Добавьте позиции по одной или нажмите /done когда закончите.")

def main(): app = ApplicationBuilder().token(TOKEN).build()

# Handlers
app.add_handler(CommandHandler('start', start))
new_member_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member)],
    states={ASK_DOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_dob)],
            ASK_WISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_wish),
                       CommandHandler('done', done_wish)]},
    fallbacks=[CommandHandler('cancel', cancel)],
)
app.add_handler(new_member_conv)

# Wish commands
app.add_handler(CommandHandler('show_wish', show_wish))
app.add_handler(CommandHandler('delete_wish', delete_wish))
app.add_handler(CommandHandler('list_birthdays', list_birthdays))
app.add_handler(CommandHandler('list_all', list_birthdays_with_wish))

update_conv = ConversationHandler(
    entry_points=[CommandHandler('update_wish', update_wish_command)],
    states={UPDATE_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_choice)],
            NEW_WISH: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_wish)]},
    fallbacks=[CommandHandler('cancel', cancel)],
)
app.add_handler(update_conv)

# Admin
app.add_handler(CommandHandler('add_birthday', add_birthday))
app.add_handler(CommandHandler('set_time', set_reminder_time))

# Schedule default daily reminder at 13:00
app.job_queue.run_daily(reminder_job, time=datetime.time(hour=13, minute=0), context=None)

app.run_polling()

if name == 'main': main()

