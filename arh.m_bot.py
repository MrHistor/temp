import json
import logging
import re
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    BotCommand,
    ChatMemberUpdated,
    ChatMember
)
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ChatMemberHandler
)
from telegram.constants import ParseMode, ChatMemberStatus

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файлы для хранения данных
BIRTHDAYS_FILE = "birthdays.json"
WISHLISTS_FILE = "wishlists.json"
ADMIN_USERNAME = "mr_jasp"  # Администратор бота

# Загрузка данных из JSON
def load_data(filename: str) -> Dict:
    try:
        if os.path.exists(filename):
            with open(filename, "r") as f:
                return json.load(f)
        return {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Сохранение данных в JSON
def save_data(data: Dict, filename: str):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# Цензура текста
def censor_text(text: str) -> str:
    forbidden_words = ["мат1", "мат2", "оскорбление"]  # Замените на реальные плохие слова
    for word in forbidden_words:
        text = re.sub(re.escape(word), "***", text, flags=re.IGNORECASE)
    return text

# Проверка формата даты
def is_valid_date(date_str: str) -> bool:
    try:
        day, month = map(int, date_str.split('.'))
        if 1 <= month <= 12 and 1 <= day <= 31:
            # Проверка существования даты (игнорируем високосные года)
            datetime(year=2000, month=month, day=day)
            return True
    except (ValueError, TypeError):
        return False
    return False

# ====================== Обработчики команд ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.chat.type == "private":
        await update.message.reply_text(
            "Привет! Я бот для управления днями рождения и wish-листами.\n"
            "Добавь меня в группу, чтобы я мог напоминать о днях рождения!"
        )
    else:
        await update.message.reply_text(
            f"Привет, {user.mention_html()}! Я бот для напоминаний о днях рождения.\n\n"
            "Я буду:\n"
            "• Напоминать о днях рождения за 2 недели и в сам день\n"
            "• Помогать вести wish-листы\n"
            "• Приветствовать новых участников\n\n"
            "Пожалуйста, напиши мне в ЛС (/start) чтобы указать свою дату рождения.",
            parse_mode=ParseMode.HTML
        )

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_members = update.message.new_chat_members
    bot_username = context.bot.username
    for member in new_members:
        if member.id == context.bot.id:  # Бота добавили в группу
            await update.message.reply_text(
                "Привет всем! Я бот для напоминаний о днях рождения.\n\n"
                "Мои функции:\n"
                "• Напоминаю о ДР за 2 недели и в день рождения\n"
                "• Помогаю вести wish-листы\n"
                "• Приветствую новых участников\n\n"
                f"Пожалуйста, напишите мне в ЛС (@{bot_username}) чтобы указать свою дату рождения!"
            )
        else:  # Новый участник группы
            await update.message.reply_text(
                f"Добро пожаловать, {member.mention_html()}!\n"
                f"Пожалуйста, напишите мне в личные сообщения (@{bot_username}) "
                "чтобы указать свою дату рождения и создать wish-лист.",
                parse_mode=ParseMode.HTML
            )

async def setup_commands(application: Application):
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("my_wishlist", "Мой wish-лист"),
        BotCommand("update_wishlist", "Обновить wish-лист"),
        BotCommand("delete_wishlist", "Удалить wish-лист"),
        BotCommand("birthdays", "Все дни рождения"),
        BotCommand("add_birthday", "Добавить ДР (админ)"),
        BotCommand("set_reminder_time", "Настройка времени (админ)"),
    ]
    await application.bot.set_my_commands(commands)

# ====================== Wish-лист ======================

async def show_wishlist_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wishlists = load_data(WISHLISTS_FILE)
    
    if user_id not in wishlists or not wishlists[user_id]:
        keyboard = [
            [InlineKeyboardButton("Создать wish-лист", callback_data="create_wishlist")]
        ]
        await update.message.reply_text(
            "У вас нет wish-листа.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        items = "\n".join(
            [f"{i+1}. {item}" for i, item in enumerate(wishlists[user_id])]
        )
        keyboard = [
            [InlineKeyboardButton("Обновить wish-лист", callback_data="update_wishlist")],
            [InlineKeyboardButton("Удалить wish-лист", callback_data="delete_wishlist")]
        ]
        await update.message.reply_text(
            f"Ваш wish-лист:\n{items}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def create_wishlist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["wishlist_state"] = "awaiting_first_item"
    await query.edit_message_text("Введите первую позицию для вашего wish-листа:")

async def add_wishlist_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = censor_text(update.message.text.strip())
    
    wishlists = load_data(WISHLISTS_FILE)
    
    if user_id not in wishlists:
        wishlists[user_id] = []
    
    wishlists[user_id].append(text)
    save_data(wishlists, WISHLISTS_FILE)
    
    keyboard = [
        [InlineKeyboardButton("Добавить еще", callback_data="add_more_items")],
        [InlineKeyboardButton("Завершить", callback_data="finish_wishlist")]
    ]
    await update.message.reply_text(
        "Позиция добавлена!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def wishlist_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(query.from_user.id)
    wishlists = load_data(WISHLISTS_FILE)
    
    if data == "add_more_items":
        context.user_data["wishlist_state"] = "awaiting_item"
        await query.edit_message_text("Введите следующую позицию:")
    
    elif data == "finish_wishlist":
        items = "\n".join([f"{i+1}. {item}" for i, item in enumerate(wishlists[user_id])])
        await query.edit_message_text(f"Ваш wish-лист создан:\n{items}")
        if "wishlist_state" in context.user_data:
            del context.user_data["wishlist_state"]
    
    elif data == "update_wishlist":
        if user_id in wishlists and wishlists[user_id]:
            keyboard = []
            for i, item in enumerate(wishlists[user_id]):
                keyboard.append([InlineKeyboardButton(f"{i+1}. {item[:10]}...", callback_data=f"edit_{i}")])
            keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
            await query.edit_message_text(
                "Выберите позицию для редактирования:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text("Ваш wish-лист пуст.")
    
    elif data.startswith("edit_"):
        index = int(data.split("_")[1])
        context.user_data["edit_index"] = index
        context.user_data["wishlist_state"] = "awaiting_edit"
        await query.edit_message_text("Введите новую позицию:")
    
    elif data == "cancel":
        await query.edit_message_text("Обновление отменено.")

async def handle_wishlist_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = censor_text(update.message.text.strip())
    wishlists = load_data(WISHLISTS_FILE)
    
    if "edit_index" in context.user_data:
        index = context.user_data["edit_index"]
        wishlists[user_id][index] = text
        save_data(wishlists, WISHLISTS_FILE)
        del context.user_data["edit_index"]
        if "wishlist_state" in context.user_data:
            del context.user_data["wishlist_state"]
        
        items = "\n".join([f"{i+1}. {item}" for i, item in enumerate(wishlists[user_id])])
        await update.message.reply_text(f"Позиция обновлена! Ваш wish-лист:\n{items}")

async def delete_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wishlists = load_data(WISHLISTS_FILE)
    
    if user_id in wishlists:
        del wishlists[user_id]
        save_data(wishlists, WISHLISTS_FILE)
        await update.message.reply_text("Ваш wish-лист удален!")
    else:
        await update.message.reply_text("У вас нет wish-листа.")

# ====================== Дни рождения ======================

async def request_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пожалуйста, введите вашу дату рождения в формате ДД.ММ (например, 15.05):"
    )
    context.user_data["awaiting_birthday"] = True

async def handle_birthday_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    
    if not is_valid_date(text):
        await update.message.reply_text("Неверный формат даты. Используйте ДД.ММ (например, 15.05)")
        return
    
    birthdays = load_data(BIRTHDAYS_FILE)
    birthdays[user_id] = text
    save_data(birthdays, BIRTHDAYS_FILE)
    
    if "awaiting_birthday" in context.user_data:
        del context.user_data["awaiting_birthday"]
    await update.message.reply_text("Дата рождения сохранена! Теперь создайте wish-лист с помощью /my_wishlist")

async def show_all_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birthdays = load_data(BIRTHDAYS_FILE)
    wishlists = load_data(WISHLISTS_FILE)
    
    if not birthdays:
        await update.message.reply_text("Пока нет сохраненных дней рождения.")
        return
    
    response = "🎂 Дни рождения участников:\n\n"
    for uid, date in birthdays.items():
        try:
            user = await context.bot.get_chat(uid)
            name = user.first_name or user.username or f"Пользователь {uid}"
            response += f"• {name}: {date}"
            
            if uid in wishlists and wishlists[uid]:
                response += " [есть wish-лист]"
            response += "\n"
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе {uid}: {e}")
            continue
    
    await update.message.reply_text(response)

# ====================== Админские команды ======================

async def add_birthday_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("У вас нет прав для этой команды.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Использование: /add_birthday [user_id] [ДД.ММ]")
        return
    
    user_id, date = context.args
    if not is_valid_date(date):
        await update.message.reply_text("Неверный формат даты. Используйте ДД.ММ")
        return
    
    birthdays = load_data(BIRTHDAYS_FILE)
    birthdays[user_id] = date
    save_data(birthdays, BIRTHDAYS_FILE)
    await update.message.reply_text(f"День рождения для {user_id} добавлен!")

# ====================== Напоминания ======================

async def birthday_reminder(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    today_str = now.strftime("%d.%m")
    
    # Рассчитать дату через 2 недели
    in_two_weeks = (now + timedelta(days=14)).strftime("%d.%m")
    
    birthdays = load_data(BIRTHDAYS_FILE)
    wishlists = load_data(WISHLISTS_FILE)
    
    # Ищем именинников
    today_birthday_users = [uid for uid, date in birthdays.items() if date == today_str]
    future_birthday_users = [uid for uid, date in birthdays.items() if date == in_two_weeks]
    
    # Отправка напоминаний
    for uid in today_birthday_users:
        try:
            await context.bot.send_message(
                int(uid),
                "🎉 С Днем Рождения! 🎂\n\n"
                "Не забудьте обновить ваш wish-лист с помощью /update_wishlist"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")
    
    for uid in future_birthday_users:
        try:
            await context.bot.send_message(
                int(uid),
                f"Через 2 недели ({in_two_weeks}) у вас День Рождения!\n"
                "Проверьте ваш wish-лист: /my_wishlist"
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания: {e}")

# ====================== Основная функция ======================

def main():
    # Загрузка токена из файла
    with open("token.txt", "r") as f:
        token = f.read().strip()
    
    application = Application.builder().token(token).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("my_wishlist", show_wishlist_menu))
    application.add_handler(CommandHandler("delete_wishlist", delete_wishlist))
    application.add_handler(CommandHandler("birthdays", show_all_birthdays))
    application.add_handler(CommandHandler("add_birthday", add_birthday_admin))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_birthday_input),
        group=1
    )
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        add_wishlist_item),
        group=2
    )
    
    # Обработчики callback-кнопок
    application.add_handler(CallbackQueryHandler(create_wishlist_start, pattern="^create_wishlist$"))
    application.add_handler(CallbackQueryHandler(wishlist_button_handler, pattern="^(add_more_items|finish_wishlist|update_wishlist|edit_\d+|cancel)$"))
    
    # Обработчик новых участников
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    
    # Запланированные задачи (напоминания)
    job_queue = application.job_queue
    job_queue.run_daily(birthday_reminder, time=datetime.strptime("13:00", "%H:%M").time())
    
   
    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
