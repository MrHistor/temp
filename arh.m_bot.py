import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext,
    ConversationHandler,
)
from telegram.constants import ParseMode
import re

# Константы для состояний ConversationHandler
GET_BIRTHDATE, GET_WISHLIST, UPDATE_WISHLIST, UPDATE_BIRTHDATE = range(4)

# Файлы для хранения данных
BIRTHDAYS_FILE = 'birthdays.json'
WISHLISTS_FILE = 'wishlists.json'

# Загрузка данных из файлов
def load_data(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# Сохранение данных в файлы
def save_data(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Загрузка данных при старте
birthdays = load_data(BIRTHDAYS_FILE)
wishlists = load_data(WISHLISTS_FILE)

# Проверка даты на корректность
def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, '%d.%m.%Y')
        return True
    except ValueError:
        return False

# Проверка текста на цензуру (простой пример)
def is_clean(text):
    forbidden_words = ['мат', 'оскорбление', 'запрещенное слово']  # Добавьте свои слова
    for word in forbidden_words:
        if word.lower() in text.lower():
            return False
    return True

# Обработчик команды /start
def start(update: Update, context: CallbackContext) -> None:
    user_id = str(update.effective_user.id)
    
    if user_id not in birthdays:
        update.message.reply_text(
            "Привет! Я бот для напоминания о днях рождения.\n"
            "Пожалуйста, введите свою дату рождения в формате ДД.ММ.ГГГГ:"
        )
        return GET_BIRTHDATE
    else:
        show_main_menu(update, context)
        return ConversationHandler.END

# Получение даты рождения
def get_birthdate(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if not is_valid_date(text):
        update.message.reply_text("Некорректный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
        return GET_BIRTHDATE
    
    birthdays[user_id] = text
    save_data(BIRTHDAYS_FILE, birthdays)
    
    update.message.reply_text(
        "Спасибо! Теперь введите ваш wishlist (что бы вы хотели получить в подарок):"
    )
    return GET_WISHLIST

# Получение wishlist
def get_wishlist(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if not is_clean(text):
        update.message.reply_text("Ваше сообщение содержит запрещенные слова. Пожалуйста, измените текст:")
        return GET_WISHLIST
    
    wishlists[user_id] = text
    save_data(WISHLISTS_FILE, wishlists)
    
    update.message.reply_text("Спасибо! Ваши данные сохранены.")
    show_main_menu(update, context)
    return ConversationHandler.END

# Показ главного меню
def show_main_menu(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Посмотреть wishlist", callback_data='view_wishlist'),
            InlineKeyboardButton("Обновить wishlist", callback_data='update_wishlist'),
        ],
        [
            InlineKeyboardButton("Удалить wishlist", callback_data='delete_wishlist'),
            InlineKeyboardButton("Посмотреть дни рождения", callback_data='view_birthdays'),
        ],
        [
            InlineKeyboardButton("Изменить дату рождения", callback_data='update_birthdate'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Обработчик кнопок
def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    user_id = str(query.from_user.id)
    
    if query.data == 'view_wishlist':
        if user_id in wishlists:
            query.edit_message_text(f"Ваш wishlist:\n{wishlists[user_id]}")
        else:
            query.edit_message_text("У вас нет сохраненного wishlist.")
    
    elif query.data == 'update_wishlist':
        query.edit_message_text("Пожалуйста, введите новый wishlist:")
        return UPDATE_WISHLIST
    
    elif query.data == 'delete_wishlist':
        if user_id in wishlists:
            del wishlists[user_id]
            save_data(WISHLISTS_FILE, wishlists)
            query.edit_message_text("Ваш wishlist удален.")
        else:
            query.edit_message_text("У вас нет сохраненного wishlist.")
    
    elif query.data == 'view_birthdays':
        if not birthdays:
            query.edit_message_text("Пока нет сохраненных дней рождения.")
        else:
            text = "Дни рождения участников:\n"
            for uid, date in birthdays.items():
                try:
                    user = context.bot.get_chat(uid)
                    name = user.first_name or user.username or "Неизвестный пользователь"
                    text += f"{name}: {date}\n"
                except:
                    text += f"Пользователь {uid}: {date}\n"
            query.edit_message_text(text)
    
    elif query.data == 'update_birthdate':
        query.edit_message_text("Пожалуйста, введите новую дату рождения в формате ДД.ММ.ГГГГ:")
        return UPDATE_BIRTHDATE
    
    show_main_menu_from_query(query, context)
    return ConversationHandler.END

# Обновление wishlist
def update_wishlist(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if not is_clean(text):
        update.message.reply_text("Ваше сообщение содержит запрещенные слова. Пожалуйста, измените текст:")
        return UPDATE_WISHLIST
    
    wishlists[user_id] = text
    save_data(WISHLISTS_FILE, wishlists)
    
    update.message.reply_text("Ваш wishlist обновлен!")
    show_main_menu(update, context)
    return ConversationHandler.END

# Обновление даты рождения
def update_birthdate(update: Update, context: CallbackContext) -> int:
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if not is_valid_date(text):
        update.message.reply_text("Некорректный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ:")
        return UPDATE_BIRTHDATE
    
    birthdays[user_id] = text
    save_data(BIRTHDAYS_FILE, birthdays)
    
    update.message.reply_text("Ваша дата рождения обновлена!")
    show_main_menu(update, context)
    return ConversationHandler.END

# Показ главного меню из query
def show_main_menu_from_query(query: Update.callback_query, context: CallbackContext) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Посмотреть wishlist", callback_data='view_wishlist'),
            InlineKeyboardButton("Обновить wishlist", callback_data='update_wishlist'),
        ],
        [
            InlineKeyboardButton("Удалить wishlist", callback_data='delete_wishlist'),
            InlineKeyboardButton("Посмотреть дни рождения", callback_data='view_birthdays'),
        ],
        [
            InlineKeyboardButton("Изменить дату рождения", callback_data='update_birthdate'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# Проверка дней рождения и отправка напоминаний
def check_birthdays(context: CallbackContext) -> None:
    now = datetime.now()
    today = now.strftime('%d.%m')
    year = now.strftime('%Y')
    
    # Проверка на напоминание за 2 недели
    future_date = (now + timedelta(days=14)).strftime('%d.%m')
    
    for user_id, birthdate_str in birthdays.items():
        try:
            birthdate = datetime.strptime(birthdate_str, '%d.%m.%Y')
            birthdate_this_year = birthdate.replace(year=int(year)).strftime('%d.%m')
            
            # Напоминание за 2 недели
            if birthdate_this_year == future_date:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.first_name or user.username or "Участник"
                    message = (
                        f"Через 2 недели ({birthdate_str[:-5]}) день рождения у {name}!\n"
                        f"Wishlist: {wishlists.get(user_id, 'не указан')}"
                    )
                    context.bot.send_message(chat_id=user_id, text=message)
                except Exception as e:
                    print(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")
            
            # Напоминание в день рождения
            elif birthdate_this_year == today:
                try:
                    user = context.bot.get_chat(user_id)
                    name = user.first_name or user.username or "Участник"
                    message = f"Сегодня день рождения у {name}! 🎉🎂\nПоздравьте их!"
                    context.bot.send_message(chat_id=user_id, text=message)
                except Exception as e:
                    print(f"Ошибка при отправке поздравления пользователю {user_id}: {e}")
        except ValueError:
            print(f"Некорректная дата рождения для пользователя {user_id}: {birthdate_str}")

# Обработчик новых участников группы
def new_member(update: Update, context: CallbackContext) -> None:
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            update.message.reply_text(
                "Привет! Я бот для напоминания о днях рождения. "
                "Я буду напоминать о днях рождения участников и собирать wishlists."
            )
        else:
            user_id = str(member.id)
            if user_id not in birthdays:
                context.bot.send_message(
                    chat_id=user_id,
                    text="Привет! Пожалуйста, введите свою дату рождения в формате ДД.ММ.ГГГГ:"
                )
                return GET_BIRTHDATE

# Основная функция
def main() -> None:
    # Создаем Updater и передаем ему токен вашего бота
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN", use_context=True)

    # Получаем диспетчер для регистрации обработчиков
    dp = updater.dispatcher

    # ConversationHandler для обработки диалогов
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member)
        ],
        states={
            GET_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthdate)],
            GET_WISHLIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wishlist)],
            UPDATE_WISHLIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_wishlist)],
            UPDATE_BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_birthdate)],
        },
        fallbacks=[],
    )

    # Регистрируем обработчики
    dp.add_handler(conv_handler)
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем проверку дней рождения каждый день в 13:00
    job_queue = updater.job_queue
    job_queue.run_daily(check_birthdays, time=datetime.time(hour=13, minute=0))

    # Запускаем бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
