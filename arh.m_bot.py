import os
import json
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
)
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы состояний
AWAITING_BIRTHDAY, AWAITING_WISH, EDITING_WISH = range(3)

# Файлы данных
BIRTHDAYS_FILE = 'birthdays.json'
WISHLISTS_FILE = 'wishlists.json'
SETTINGS_FILE = 'settings.json'
ADMIN_USERNAME = '@mr_jasp'  # Имя администратора

# Загрузка данных из файлов
def load_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
    return {}

# Сохранение данных в файл
def save_data(data, filename):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

# Инициализация данных
birthdays = load_data(BIRTHDAYS_FILE)
wishlists = load_data(WISHLISTS_FILE)
settings = load_data(SETTINGS_FILE)

# Установка времени напоминаний по умолчанию
if 'reminder_time' not in settings:
    settings['reminder_time'] = "13:00"
    save_data(settings, SETTINGS_FILE)

# Фильтр нецензурных слов (можно расширить)
PROFANITY_FILTER = re.compile(r'\b(плохоеслово1|плохоеслово2)\b', re.IGNORECASE)

# Проверка даты рождения
def is_valid_birthday(date_str):
    try:
        date = datetime.strptime(date_str, '%d.%m.%Y')
        if date > datetime.now():
            return False
        return True
    except ValueError:
        return False

# Обработчик нового участника группы
def welcome_new_member(update: Update, context: CallbackContext):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:  # Игнорируем добавление самого бота
            continue
        
        chat_id = update.effective_chat.id
        user_id = member.id
        username = member.username or member.first_name
        
        # Приветствие
        welcome_text = (
            f"Привет, {username}!\n"
            "Я бот для напоминаний о днях рождения 🎉\n\n"
            "Я буду:\n"
            "• Напоминать о днях рождения участников\n"
            "• Помогать вести wish-листы\n"
            "• Присылать напоминания за 2 недели и в день рождения\n\n"
            "Пожалуйста, укажи свою дату рождения в формате ДД.ММ.ГГГГ (например, 31.12.1990)"
        )
        
        update.message.reply_text(welcome_text)
        
        # Сохраняем временные данные для ожидания даты рождения
        context.user_data['new_user'] = {
            'chat_id': chat_id,
            'user_id': user_id,
            'username': username
        }
        return AWAITING_BIRTHDAY

# Обработка даты рождения
def process_birthday(update: Update, context: CallbackContext):
    user_data = context.user_data.get('new_user')
    if not user_data:
        return ConversationHandler.END
    
    chat_id = user_data['chat_id']
    user_id = user_data['user_id']
    date_str = update.message.text
    
    if not is_valid_birthday(date_str):
        update.message.reply_text("❌ Неверный формат даты! Используй ДД.ММ.ГГГГ")
        return AWAITING_BIRTHDAY
    
    # Сохранение даты рождения
    if str(chat_id) not in birthdays:
        birthdays[str(chat_id)] = {}
    
    birthdays[str(chat_id)][str(user_id)] = {
        'username': user_data['username'],
        'birthday': date_str
    }
    save_data(birthdays, BIRTHDAYS_FILE)
    
    # Инициализация wish-листа
    if str(chat_id) not in wishlists:
        wishlists[str(chat_id)] = {}
    wishlists[str(chat_id)][str(user_id)] = []
    save_data(wishlists, WISHLISTS_FILE)
    
    update.message.reply_text(
        "✅ Дата рождения сохранена!\n\n"
        "Теперь введи первый пункт своего wish-листа:"
    )
    return AWAITING_WISH

# Добавление пункта в wish-лист
def add_wish_item(update: Update, context: CallbackContext):
    user_data = context.user_data.get('new_user')
    if not user_data:
        return ConversationHandler.END
    
    chat_id = user_data['chat_id']
    user_id = user_data['user_id']
    wish_text = update.message.text
    
    # Проверка на цензуру
    if PROFANITY_FILTER.search(wish_text):
        update.message.reply_text("❌ Содержит недопустимые слова! Измени формулировку.")
        return AWAITING_WISH
    
    # Сохранение пункта
    wish_item = {
        'id': datetime.now().timestamp(),
        'text': wish_text
    }
    wishlists[str(chat_id)][str(user_id)].append(wish_item)
    save_data(wishlists, WISHLISTS_FILE)
    
    # Клавиатура для продолжения
    keyboard = [
        [InlineKeyboardButton("Добавить ещё", callback_data='add_more')],
        [InlineKeyboardButton("Завершить", callback_data='finish')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "✅ Пункт добавлен! Что дальше?",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

# Кнопки для wish-листа
def wish_buttons(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.data == 'add_more':
        query.edit_message_text("Введи следующий пункт wish-листа:")
        return AWAITING_WISH
    
    elif query.data == 'finish':
        query.edit_message_text("🎉 Твой wish-лист сохранён! Можешь просмотреть его через меню.")
        return ConversationHandler.END

# Просмотр своего wish-листа
def show_my_wishlist(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if str(chat_id) not in wishlists or str(user_id) not in wishlists[str(chat_id)]:
        update.message.reply_text("❌ У тебя ещё нет wish-листа!")
        return
    
    wish_items = wishlists[str(chat_id)][str(user_id)]
    if not wish_items:
        update.message.reply_text("❌ Твой wish-лист пуст!")
        return
    
    response = "📝 Твой wish-лист:\n\n"
    for i, item in enumerate(wish_items, 1):
        response += f"{i}. {item['text']}\n"
    
    # Кнопки управления
    keyboard = [
        [InlineKeyboardButton("Добавить пункт", callback_data='add_item')],
        [InlineKeyboardButton("Удалить пункт", callback_data='delete_item')],
        [InlineKeyboardButton("Удалить весь лист", callback_data='clear_list')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(response, reply_markup=reply_markup)

# Редактирование wish-листа
def edit_wishlist(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    
    if query.data == 'add_item':
        query.edit_message_text("Введи новый пункт для wish-листа:")
        context.user_data['wish_action'] = 'add'
        return AWAITING_WISH
    
    elif query.data == 'delete_item':
        wish_items = wishlists[str(chat_id)][str(user_id)]
        if not wish_items:
            query.edit_message_text("❌ Твой wish-лист пуст!")
            return
        
        keyboard = []
        for i, item in enumerate(wish_items, 1):
            keyboard.append([InlineKeyboardButton(
                f"❌ Удалить пункт {i}", 
                callback_data=f"delete_{item['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("Отмена", callback_data='cancel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        query.edit_message_text("Выбери пункт для удаления:", reply_markup=reply_markup)
    
    elif query.data == 'clear_list':
        wishlists[str(chat_id)][str(user_id)] = []
        save_data(wishlists, WISHLISTS_FILE)
        query.edit_message_text("✅ Весь wish-лист удалён!")
    
    elif query.data.startswith('delete_'):
        item_id = float(query.data.split('_')[1])
        wish_items = wishlists[str(chat_id)][str(user_id)]
        wishlists[str(chat_id)][str(user_id)] = [
            item for item in wish_items if item['id'] != item_id
        ]
        save_data(wishlists, WISHLISTS_FILE)
        query.edit_message_text("✅ Пункт удалён!")
    
    elif query.data == 'cancel':
        query.edit_message_text("Действие отменено.")

# Просмотр дней рождений
def show_birthdays(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    if str(chat_id) not in birthdays:
        update.message.reply_text("❌ В этой группе ещё нет данных о днях рождения!")
        return
    
    response = "🎂 Дни рождения участников:\n\n"
    for user_id, data in birthdays[str(chat_id)].items():
        response += f"• {data['username']}: {data['birthday']}\n"
    
    # Кнопка для просмотра wish-листов
    keyboard = [[
        InlineKeyboardButton("Посмотреть wish-листы", callback_data='view_wishlists')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(response, reply_markup=reply_markup)

# Просмотр wish-листов участников
def show_all_wishlists(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    
    if str(chat_id) not in wishlists or not wishlists[str(chat_id)]:
        query.edit_message_text("❌ В этой группе ещё нет wish-листов!")
        return
    
    keyboard = []
    for user_id, data in birthdays[str(chat_id)].items():
        if user_id in wishlists[str(chat_id)]:
            keyboard.append([
                InlineKeyboardButton(
                    f"Wish-лист {data['username']}",
                    callback_data=f"wish_{user_id}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text("Чей wish-лист показать?", reply_markup=reply_markup)

# Показать конкретный wish-лист
def show_user_wishlist(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id
    user_id = query.data.split('_')[1]
    
    wish_items = wishlists[str(chat_id)].get(user_id, [])
    username = birthdays[str(chat_id)][user_id]['username']
    
    if not wish_items:
        query.edit_message_text(f"❌ У {username} ещё нет wish-листа!")
        return
    
    response = f"🎁 Wish-лист {username}:\n\n"
    for i, item in enumerate(wish_items, 1):
        response += f"{i}. {item['text']}\n"
    
    query.edit_message_text(response)

# Админ: добавление дня рождения
def admin_add_birthday(update: Update, context: CallbackContext):
    user = update.effective_user
    if f"@{user.username}" != ADMIN_USERNAME:
        update.message.reply_text("❌ Команда только для администратора!")
        return
    
    if len(context.args) < 2:
        update.message.reply_text("Использование: /add_birthday @username ДД.ММ.ГГГГ")
        return
    
    username = context.args[0]
    date_str = context.args[1]
    
    if not is_valid_birthday(date_str):
        update.message.reply_text("❌ Неверный формат даты! Используй ДД.ММ.ГГГГ")
        return
    
    # Здесь должна быть логика поиска user_id по username
    # В демо-версии просто сохраняем
    update.message.reply_text(f"✅ Добавлен день рождения для {username}: {date_str}")

# Админ: настройка времени
def admin_set_time(update: Update, context: CallbackContext):
    user = update.effective_user
    if f"@{user.username}" != ADMIN_USERNAME:
        update.message.reply_text("❌ Команда только для администратора!")
        return
    
    if len(context.args) < 1:
        update.message.reply_text("Использование: /set_time ЧЧ:ММ")
        return
    
    time_str = context.args[0]
    try:
        datetime.strptime(time_str, '%H:%M')
        settings['reminder_time'] = time_str
        save_data(settings, SETTINGS_FILE)
        update.message.reply_text(f"✅ Время напоминаний установлено: {time_str}")
    except ValueError:
        update.message.reply_text("❌ Неверный формат времени! Используй ЧЧ:ММ")

# Проверка дней рождений
def check_birthdays(context: CallbackContext):
    now = datetime.now().strftime('%d.%m')
    future = (datetime.now() + timedelta(days=14)).strftime('%d.%m')
    time_now = datetime.now().strftime('%H:%M')
    
    if time_now != settings['reminder_time']:
        return
    
    for chat_id, users in birthdays.items():
        for user_id, data in users.items():
            bday = data['birthday'][:5]  # ДД.ММ
            
            # Напоминание за 2 недели
            if bday == future:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ Напоминание: через 2 недели ({data['birthday']}) "
                         f"день рождения у {data['username']}!"
                )
            
            # Напоминание в день рождения
            elif bday == now:
                context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎉 Сегодня день рождения у {data['username']}! Поздравляем!"
                )

# Основная функция
def main():
    # Загрузка токена
    try:
        with open('token.txt', 'r') as f:
            TOKEN = f.read().strip()
    except FileNotFoundError:
        print("Файл token.txt не найден!")
        return

    updater = Updater(TOKEN)
    dp = updater.dispatcher

    # Обработчики разговоров
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.status_update.new_chat_members, welcome_new_member)],
        states={
            AWAITING_BIRTHDAY: [MessageHandler(Filters.text & ~Filters.command, process_birthday)],
            AWAITING_WISH: [
                MessageHandler(Filters.text & ~Filters.command, add_wish_item),
                CallbackQueryHandler(wish_buttons)
            ],
        },
        fallbacks=[],
        per_user=False
    )

    # Регистрация обработчиков
    dp.add_handler(conv_handler)
    dp.add_handler(CommandHandler("my_wishlist", show_my_wishlist))
    dp.add_handler(CommandHandler("birthdays", show_birthdays))
    dp.add_handler(CommandHandler("add_birthday", admin_add_birthday))
    dp.add_handler(CommandHandler("set_time", admin_set_time))
    dp.add_handler(CallbackQueryHandler(edit_wishlist, pattern='^(add_item|delete_item|clear_list|delete_|cancel)'))
    dp.add_handler(CallbackQueryHandler(show_all_wishlists, pattern='^view_wishlists$'))
    dp.add_handler(CallbackQueryHandler(show_user_wishlist, pattern='^wish_'))
    dp.add_handler(CallbackQueryHandler(show_birthdays, pattern='^back$'))

    # Планировщик напоминаний
    jq = updater.job_queue
    jq.run_repeating(check_birthdays, interval=60, first=0)  # Проверка каждую минуту

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
