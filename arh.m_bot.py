import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from telegram import (
    Update,
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)
from telegram.constants import ParseMode

# Конфигурация
BIRTHDAYS_FILE = "birthdays.json"
WISHLISTS_FILE = "wishlists.json"
TOKEN_FILE = "token.txt"
ADMIN_USERNAME = "mr_jasp"  # Без @
REMINDER_HOUR = 13  # Время напоминаний по умолчанию (13:00)

# Состояния для ConversationHandler
GETTING_BIRTHDAY, GETTING_WISH, ADDING_WISH, EDITING_WISH, DELETING_WISH, ADMIN_ADD_BIRTHDAY, ADMIN_SET_TIME = range(7)

# Инициализация логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка данных
def load_data(filename: str) -> Dict[str, Any]:
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return {}

# Сохранение данных
def save_data(data: Dict[str, Any], filename: str):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

# Фильтр нецензурной лексики
def censor_text(text: str) -> str:
    bad_words = ["мат1", "мат2", "мат3"]  # Заменить на реальный список
    for word in bad_words:
        text = re.sub(rf"\b{word}\b", "***", text, flags=re.IGNORECASE)
    return text

# Проверка даты рождения
def is_valid_birthday(date_str: str) -> bool:
    try:
        day, month = map(int, date_str.split("."))
        if 1 <= month <= 12 and 1 <= day <= 31:
            datetime(year=2000, month=month, day=day)  # Проверка корректности даты
            return True
    except (ValueError, TypeError):
        return False
    return False

# Основные функции бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.chat.type == "private":
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Привет, {user.first_name}! Я бот для управления днями рождения и wish-листами.\n"
            "В группе я буду напоминать о предстоящих днях рождения.\n\n"
            "Пожалуйста, введи свою дату рождения в формате ДД.ММ (например, 15.05):",
        )
        return GETTING_BIRTHDAY
    return ConversationHandler.END

async def get_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    date_str = update.message.text.strip()
    
    if not is_valid_birthday(date_str):
        await update.message.reply_text("❌ Неверный формат даты. Пожалуйста, введи дату в формате ДД.ММ (например, 15.05):")
        return GETTING_BIRTHDAY
    
    birthdays = load_data(BIRTHDAYS_FILE)
    birthdays[str(user.id)] = {
        "date": date_str,
        "name": user.full_name
    }
    save_data(birthdays, BIRTHDAYS_FILE)
    
    await update.message.reply_text(
        "✅ Дата рождения сохранена! Теперь введи первый пункт твоего wish-листа:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return GETTING_WISH

async def get_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wish = censor_text(update.message.text.strip())
    
    wishlists = load_data(WISHLISTS_FILE)
    wishlists[str(user.id)] = [wish]
    save_data(wishlists, WISHLISTS_FILE)
    
    await update.message.reply_text(
        "✅ Первый пункт добавлен! Ты можешь добавить ещё пункты или использовать меню:",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END

async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        if user.id == context.bot.id:
            await update.message.reply_text(
                "Привет всем! Я бот для напоминаний о днях рождения 🎂\n\n"
                "Я буду:\n"
                "• Напоминать за 2 недели и в день рождения\n"
                "• Помогать вести wish-листы\n\n"
                "Для работы со мной нужно:\n"
                "1. Написать мне в ЛС /start\n"
                "2. Ввести дату рождения\n"
                "3. Создать свой wish-лист\n\n"
                "Управление через меню в личном чате со мной!"
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"Привет, {user.first_name}! Добро пожаловать в группу!\n"
                "Для использования бота дней рождения напиши мне /start в личном чате."
            )

async def show_my_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wishlists = load_data(WISHLISTS_FILE)
    
    if str(user.id) not in wishlists or not wishlists[str(user.id)]:
        await update.message.reply_text("❌ Твой wish-лист пуст!")
        return
    
    wishes = "\n".join(
        f"{i+1}. {wish}" for i, wish in enumerate(wishlists[str(user.id)])
    
    await update.message.reply_text(
        f"📝 Твой wish-лист:\n\n{wishes}",
        reply_markup=get_main_keyboard(),
    )

async def delete_my_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wishlists = load_data(WISHLISTS_FILE)
    
    if str(user.id) not in wishlists:
        await update.message.reply_text("❌ У тебя нет wish-листа для удаления!")
        return
    
    del wishlists[str(user.id)]
    save_data(wishlists, WISHLISTS_FILE)
    
    await update.message.reply_text(
        "✅ Твой wish-лист удалён!",
        reply_markup=get_main_keyboard(),
    )

async def update_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wishlists = load_data(WISHLISTS_FILE)
    
    if str(user.id) not in wishlists or not wishlists[str(user.id)]:
        await update.message.reply_text("❌ Твой wish-лист пуст!")
        return
    
    wishes = wishlists[str(user.id)]
    keyboard = [
        [InlineKeyboardButton("Добавить пункт", callback_data="add_wish")],
        [InlineKeyboardButton("Изменить пункт", callback_data="edit_wish")],
        [InlineKeyboardButton("Удалить пункт", callback_data="delete_wish")],
    ]
    
    wish_text = "\n".join(f"{i+1}. {wish}" for i, wish in enumerate(wishes))
    
    await update.message.reply_text(
        f"📝 Твой текущий wish-лист:\n\n{wish_text}\n\nВыбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def add_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введи новый пункт для wish-листа:")
    return ADDING_WISH

async def adding_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wish = censor_text(update.message.text.strip())
    
    wishlists = load_data(WISHLISTS_FILE)
    wishlists[str(user.id)].append(wish)
    save_data(wishlists, WISHLISTS_FILE)
    
    await update.message.reply_text(
        "✅ Пункт добавлен!",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END

async def edit_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    wishlists = load_data(WISHLISTS_FILE)
    wishes = wishlists[str(user.id)]
    
    keyboard = [
        [InlineKeyboardButton(f"{i+1}. {wish[:15]}...", callback_data=f"edit_{i}")]
        for i, wish in enumerate(wishes)
    ]
    
    await query.edit_message_text(
        "Выбери пункт для изменения:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def edit_wish_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    wish_index = int(query.data.split("_")[1])
    context.user_data["wish_index"] = wish_index
    
    await query.edit_message_text("Введи новый текст для этого пункта:")
    return EDITING_WISH

async def editing_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    new_text = censor_text(update.message.text.strip())
    wish_index = context.user_data["wish_index"]
    
    wishlists = load_data(WISHLISTS_FILE)
    wishlists[str(user.id)][wish_index] = new_text
    save_data(wishlists, WISHLISTS_FILE)
    
    await update.message.reply_text(
        "✅ Пункт обновлён!",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END

async def delete_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    wishlists = load_data(WISHLISTS_FILE)
    wishes = wishlists[str(user.id)]
    
    keyboard = [
        [InlineKeyboardButton(f"{i+1}. {wish[:15]}...", callback_data=f"delete_{i}")]
        for i, wish in enumerate(wishes)
    ]
    
    await query.edit_message_text(
        "Выбери пункт для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def delete_wish_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    wish_index = int(query.data.split("_")[1])
    
    wishlists = load_data(WISHLISTS_FILE)
    wishlists[str(query.from_user.id)].pop(wish_index)
    save_data(wishlists, WISHLISTS_FILE)
    
    await query.edit_message_text(
        "✅ Пункт удалён!",
        reply_markup=get_main_keyboard(),
    )

async def show_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birthdays = load_data(BIRTHDAYS_FILE)
    if not birthdays:
        await update.message.reply_text("❌ Нет данных о днях рождения!")
        return
    
    text = "📅 Дни рождения участников:\n\n"
    keyboard = []
    
    for user_id, data in birthdays.items():
        try:
            user = await context.bot.get_chat(user_id)
            name = user.full_name
        except:
            name = data["name"]
        
        text += f"• {name}: {data['date']}\n"
        keyboard.append([InlineKeyboardButton(
            f"Wish-лист {name}",
            callback_data=f"wl_{user_id}"
        )])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def show_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.data.split("_")[1]
    wishlists = load_data(WISHLISTS_FILE)
    
    if user_id not in wishlists or not wishlists[user_id]:
        await query.edit_message_text("❌ У этого пользователя нет wish-листа!")
        return
    
    try:
        user = await context.bot.get_chat(user_id)
        name = user.full_name
    except:
        name = load_data(BIRTHDAYS_FILE).get(user_id, {}).get("name", "Unknown")
    
    wishes = "\n".join(
        f"{i+1}. {wish}" for i, wish in enumerate(wishlists[user_id]))
    
    await query.edit_message_text(
        f"🎁 Wish-лист {name}:\n\n{wishes}",
    )

# Админ-команды
async def admin_add_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Команда только для администратора!")
        return
    
    await update.message.reply_text(
        "Введи ID пользователя и дату рождения в формате: id_пользователя ДД.ММ\n"
        "Например: 123456789 15.05"
    )
    return ADMIN_ADD_BIRTHDAY

async def admin_adding_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ Неверный формат. Используй: id_пользователя ДД.ММ")
        return ADMIN_ADD_BIRTHDAY
    
    user_id = parts[0]
    date_str = parts[1]
    
    if not is_valid_birthday(date_str):
        await update.message.reply_text("❌ Неверный формат даты. Используй ДД.ММ")
        return ADMIN_ADD_BIRTHDAY
    
    birthdays = load_data(BIRTHDAYS_FILE)
    birthdays[user_id] = {
        "date": date_str,
        "name": f"Пользователь {user_id}"  # Имя будет обновлено при первом взаимодействии
    }
    save_data(birthdays, BIRTHDAYS_FILE)
    
    await update.message.reply_text("✅ Дата рождения добавлена!")
    return ConversationHandler.END

async def admin_set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Команда только для администратора!")
        return
    
    await update.message.reply_text(
        "Введи новое время для напоминаний в формате ЧЧ (от 0 до 23):"
    )
    return ADMIN_SET_TIME

async def admin_setting_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global REMINDER_HOUR
    try:
        new_hour = int(update.message.text.strip())
        if 0 <= new_hour <= 23:
            REMINDER_HOUR = new_hour
            await update.message.reply_text(f"✅ Время напоминаний установлено на {new_hour}:00!")
        else:
            await update.message.reply_text("❌ Неверное время. Используй число от 0 до 23.")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Введи число от 0 до 23.")
    
    return ConversationHandler.END

# Напоминания
async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    today_str = now.strftime("%d.%m")
    in_two_weeks = (now + timedelta(days=14)).strftime("%d.%m")
    
    birthdays = load_data(BIRTHDAYS_FILE)
    bot = context.bot
    
    for user_id, data in birthdays.items():
        try:
            # Напоминание за 2 недели
            if data["date"] == in_two_weeks:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ Напоминание: через 2 недели ({data['date']}) "
                         f"день рождения у {data['name']}!",
                    parse_mode=ParseMode.HTML
                )
            
            # Напоминание в день рождения
            if data["date"] == today_str:
                # Имениннику
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🎂 С днём рождения, {data['name']}! Не забудь обновить wish-лист!",
                    reply_markup=get_main_keyboard(),
                )
                
                # Всем остальным
                for other_id in birthdays:
                    if other_id != user_id:
                        await bot.send_message(
                            chat_id=other_id,
                            text=f"🎉 Сегодня ({data['date']}) день рождения у {data['name']}!",
                            parse_mode=ParseMode.HTML
                        )
        except Exception as e:
            logger.error(f"Error sending reminder to {user_id}: {e}")

# Вспомогательные функции
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["🎂 Мой wish-лист", "✏️ Обновить wish-лист"],
            ["🗑 Удалить wish-лист", "📅 Все дни рождения"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# Главная функция
def main():
    # Загрузка токена
    if not os.path.exists(TOKEN_FILE):
        logger.error(f"Token file {TOKEN_FILE} not found!")
        return
    
    with open(TOKEN_FILE, "r") as f:
        token = f.read().strip()
    
    # Создание приложения
    application = ApplicationBuilder().token(token).build()
    
    # Conversation Handlers
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GETTING_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthday)
            ],
            GETTING_WISH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_wish)
            ],
            ADDING_WISH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, adding_wish)
            ],
            EDITING_WISH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, editing_wish)
            ],
            ADMIN_ADD_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_adding_birthday)
            ],
            ADMIN_SET_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_setting_time)
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    
    # Регистрация обработчиков
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members))
    application.add_handler(CommandHandler("admin_add", admin_add_birthday))
    application.add_handler(CommandHandler("admin_time", admin_set_time))
    
    # Wish-лист
    application.add_handler(MessageHandler(filters.Regex(r"^🎂 Мой wish-лист$"), show_my_wishlist))
    application.add_handler(MessageHandler(filters.Regex(r"^🗑 Удалить wish-лист$"), delete_my_wishlist))
    application.add_handler(MessageHandler(filters.Regex(r"^✏️ Обновить wish-лист$"), update_wishlist))
    application.add_handler(MessageHandler(filters.Regex(r"^📅 Все дни рождения$"), show_birthdays))
    
    # Inline-обработчики
    application.add_handler(CallbackQueryHandler(add_wish, pattern="^add_wish$"))
    application.add_handler(CallbackQueryHandler(edit_wish, pattern="^edit_wish$"))
    application.add_handler(CallbackQueryHandler(delete_wish, pattern="^delete_wish$"))
    application.add_handler(CallbackQueryHandler(edit_wish_selected, pattern="^edit_"))
    application.add_handler(CallbackQueryHandler(delete_wish_selected, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(show_wishlist, pattern="^wl_"))
    
    # Планировщик напоминаний
    job_queue = application.job_queue
    job_queue.run_daily(
        send_reminders,
        time=datetime.strptime(f"{REMINDER_HOUR}:00", "%H:%M").time(),
        days=(0, 1, 2, 3, 4, 5, 6)
    )
    
    # Запуск бота
    application.run_polling()

if __name__ == "__main__":
    main()
