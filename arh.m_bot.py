import os
import json
import re
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы состояний
SET_BIRTHDAY, SET_WISHLIST, ADMIN_ADD_BIRTHDAY = range(3)
ADMIN_USERNAME = "mr_jasp"  # Имя пользователя админа

# Файлы для хранения данных
BIRTHDAYS_FILE = "birthdays.json"
WISHLISTS_FILE = "wishlists.json"
TOKEN_FILE = "token.txt"
GROUP_CHAT_ID_FILE = "group_chat_id.txt"

# Загрузка данных
def load_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

# Сохранение данных
def save_data(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Сохранение ID группы
def save_group_chat_id(chat_id):
    with open(GROUP_CHAT_ID_FILE, 'w') as f:
        f.write(str(chat_id))

# Загрузка ID группы
def load_group_chat_id():
    if os.path.exists(GROUP_CHAT_ID_FILE):
        with open(GROUP_CHAT_ID_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return None
    return None

# Инициализация данных
birthdays = load_data(BIRTHDAYS_FILE)
wishlists = load_data(WISHLISTS_FILE)
GROUP_CHAT_ID = load_group_chat_id()

# Проверка даты рождения
def is_valid_birthdate(date_str):
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y")
        return date <= datetime.now()
    except ValueError:
        return False

# Фильтр нецензурных слов
def censor_text(text):
    bad_words = ["мат1", "мат2", "мат3"]  # Замените на реальные слова
    for word in bad_words:
        text = re.sub(re.escape(word), "*цензура*", text, flags=re.IGNORECASE)
    return text

# Главное меню
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎁 Мой wish-лист", callback_data="view_wishlist")],
        [InlineKeyboardButton("✏️ Обновить wish-лист", callback_data="update_wishlist")],
        [InlineKeyboardButton("🗑️ Удалить wish-лист", callback_data="delete_wishlist")],
        [InlineKeyboardButton("📅 Все дни рождения", callback_data="all_birthdays")],
        [InlineKeyboardButton("📝 Изменить дату рождения", callback_data="change_birthday")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.chat.type == "private":
        if str(user.id) not in birthdays:
            await update.message.reply_text(
                "Привет! Укажи свою дату рождения в формате ДД.ММ.ГГГГ:"
            )
            return SET_BIRTHDAY
        else:
            await update.message.reply_text(
                "Выбери действие:",
                reply_markup=main_menu_keyboard()
            )
    return ConversationHandler.END

# Установка даты рождения
async def set_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    date_str = update.message.text.strip()
    
    if not is_valid_birthdate(date_str):
        await update.message.reply_text("Некорректная дата. Попробуй снова (ДД.ММ.ГГГГ):")
        return SET_BIRTHDAY
    
    birthdays[str(user.id)] = {
        "date": date_str,
        "username": user.username or user.full_name
    }
    save_data(birthdays, BIRTHDAYS_FILE)
    
    await update.message.reply_text(
        "Дата сохранена! Теперь отправь свой wish-лист:"
    )
    return SET_WISHLIST

# Установка wish-листа
async def set_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wishlist = censor_text(update.message.text)
    
    wishlists[str(user.id)] = wishlist
    save_data(wishlists, WISHLISTS_FILE)
    
    await update.message.reply_text(
        "Wish-лист сохранен!",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# Обработчики кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "view_wishlist":
        await view_wishlist(query)
    elif query.data == "update_wishlist":
        await update_wishlist_start(query)
    elif query.data == "delete_wishlist":
        await delete_wishlist(query, context)
    elif query.data == "all_birthdays":
        await all_birthdays(query)
    elif query.data == "change_birthday":
        await change_birthday_start(query)

# Просмотр wish-листа
async def view_wishlist(query):
    user_id = str(query.from_user.id)
    if user_id in wishlists:
        await query.edit_message_text(f"Твой wish-лист:\n{wishlists[user_id]}")
    else:
        await query.edit_message_text("У тебя нет сохраненного wish-листа.")

# Обновление wish-листа
async def update_wishlist_start(query):
    await query.edit_message_text("Отправь новый wish-лист:")
    return SET_WISHLIST

# Удаление wish-листа
async def delete_wishlist(query, context):
    user_id = str(query.from_user.id)
    if user_id in wishlists:
        del wishlists[user_id]
        save_data(wishlists, WISHLISTS_FILE)
        await query.edit_message_text("Wish-лист удален!")
    else:
        await query.edit_message_text("У тебя нет сохраненного wish-листа.")

# Список дней рождений
async def all_birthdays(query):
    if not birthdays:
        await query.edit_message_text("Дни рождения не добавлены.")
        return
    
    text = "🎂 Дни рождения участников:\n"
    for user_id, data in birthdays.items():
        text += f"\n{data['username']}: {data['date']}"
    
    await query.edit_message_text(text)

# Изменение даты рождения
async def change_birthday_start(query):
    await query.edit_message_text("Введи новую дату рождения (ДД.ММ.ГГГГ):")
    return SET_BIRTHDAY

# Напоминания
async def birthday_reminders(context: ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    if GROUP_CHAT_ID is None:
        GROUP_CHAT_ID = load_group_chat_id()
        if GROUP_CHAT_ID is None:
            return
    
    today = datetime.now().date()
    two_weeks_later = today + timedelta(days=14)
    
    for user_id, data in birthdays.items():
        try:
            bday = datetime.strptime(data["date"], "%d.%m.%Y").date()
            try:
                bday_this_year = bday.replace(year=today.year)
            except ValueError:  # Обработка 29 февраля
                bday_this_year = datetime(today.year, 3, 1).date()

            # Напоминание за 2 недели
            if bday_this_year == two_weeks_later:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=f"🎉 Через 2 недели ({bday_this_year.strftime('%d.%m')}) день рождения у {data['username']}!"
                )
            
            # Напоминание в день рождения
            if bday_this_year == today:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=f"🎂 Сегодня день рождения у {data['username']}! Поздравляем!"
                )
                
                # Запрос wish-листа за 1 месяц
                one_month_before = bday_this_year - timedelta(days=30)
                if one_month_before == today:
                    if str(user_id) in wishlists:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="Не забудь обновить свой wish-лист!"
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="Пожалуйста, добавь свой wish-лист!"
                        )
        except Exception as e:
            logger.error(f"Ошибка напоминания: {e}")

# Админские команды
async def admin_add_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("Доступ запрещен!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Перешли сообщение пользователя и укажи дату в формате: ДД.ММ.ГГГГ"
    )
    return ADMIN_ADD_BIRTHDAY

async def admin_save_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Ошибка: нужно переслать сообщение!")
        return ADMIN_ADD_BIRTHDAY
    
    try:
        # Пытаемся получить информацию о пользователе
        if update.message.reply_to_message.forward_from:
            user = update.message.reply_to_message.forward_from
        else:
            user = update.message.reply_to_message.from_user
        
        user_id = str(user.id)
        date_str = update.message.text.strip()
        
        if not is_valid_birthdate(date_str):
            await update.message.reply_text("Некорректная дата!")
            return ADMIN_ADD_BIRTHDAY
        
        birthdays[user_id] = {
            "date": date_str,
            "username": user.username or user.full_name
        }
        save_data(birthdays, BIRTHDAYS_FILE)
        await update.message.reply_text("Данные сохранены!")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        await update.message.reply_text(f"Ошибка: {str(e)}")
    
    return ConversationHandler.END

# Новые участники группы
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    
    # Сохраняем ID группы при добавлении бота
    if context.bot.id in [user.id for user in update.message.new_chat_members]:
        GROUP_CHAT_ID = update.message.chat.id
        save_group_chat_id(GROUP_CHAT_ID)
        await update.message.reply_text(
            "Бот активирован! Напишите мне в ЛС /start для регистрации."
        )
        return
    
    # Приветствие новых участников
    for member in update.message.new_chat_members:
        if not member.is_bot:
            try:
                await context.bot.send_message(
                    chat_id=member.id,
                    text="Привет! Я бот для учета дней рождения. "
                         "Напиши мне /start в личных сообщениях, "
                         "чтобы зарегистрировать свой день рождения."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение: {e}")
                await update.message.reply_text(
                    f"{member.full_name}, напиши мне в ЛС /start для регистрации!"
                )

# Отмена операции
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Операция отменена",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# Основная функция
def main():
    # Загрузка токена
    if not os.path.exists(TOKEN_FILE):
        logger.error(f"Файл {TOKEN_FILE} не найден!")
        return
    
    with open(TOKEN_FILE, 'r') as f:
        token = f.read().strip()
    
    if not token:
        logger.error("Токен не найден!")
        return

    app = Application.builder().token(token).build()
    
    # Обработчики
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member)
        ],
        states={
            SET_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_birthday),
                CommandHandler("cancel", cancel)
            ],
            SET_WISHLIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_wishlist),
                CommandHandler("cancel", cancel)
            ],
            ADMIN_ADD_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_birthday),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Регистрация обработчиков
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("admin_add", admin_add_birthday))
    
    # Ежедневные напоминания в 13:00
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_daily(
            birthday_reminders,
            time=datetime.strptime("13:00", "%H:%M").time(),
            days=(0, 1, 2, 3, 4, 5, 6)
        )
    
    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Ошибка бота: {e}")

if __name__ == "__main__":
    # Инициализация данных
    birthdays = load_data(BIRTHDAYS_FILE)
    wishlists = load_data(WISHLISTS_FILE)
    GROUP_CHAT_ID = load_group_chat_id()
    
    main()
