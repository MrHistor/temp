import os
import json
import re
import logging
from datetime import datetime, timedelta
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
SET_BIRTHDAY, ADD_WISHLIST_ITEM, UPDATE_WISHLIST, ADMIN_ADD_BIRTHDAY = range(4)
ADMIN_USERNAME = "mr_jasp" # Имя пользователя админа
VIEW_OTHERS_WISHLIST, DELETE_ITEM = range(2)
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
        except (json.JSONDecodeError, FileNotFoundError):
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

# Клавиатура главного меню (внизу экрана)
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎁 Мой wish-лист")],
            [KeyboardButton("✏️ Обновить wish-лист")],
            [KeyboardButton("🗑️ Удалить wish-лист")],
            [KeyboardButton("📅 Все дни рождения")],
            [KeyboardButton("👀 Wish-листы участников")]  # Новая кнопка
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )

# Приветственное сообщение
WELCOME_MESSAGE = """
🎉 *Добро пожаловать в Birthday Bot!* 🎂

Я помогу вам никогда не забывать о днях рождения друзей и коллег. Вот что я умею:

🔔 *Напоминания:*
- За 2 недели до дня рождения
- В сам день рождения
- За месяц до ДР напомню имениннику обновить wish-лист

📝 *Wish-лист:*
- Создайте свой список желаний
- Обновляйте его в любое время
- Просматривайте списки других участников

👥 *Для новых участников:*
- Я автоматически запрошу дату рождения
- Помогу создать wish-лист

⏰ *Все напоминания приходят в 13:00*

Начните с команды /start в личных сообщениях!
"""

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if update.message.chat.type == "private":
        # Отправляем приветственное сообщение
        await update.message.reply_text(
            WELCOME_MESSAGE,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        
        if str(user.id) not in birthdays:
            await update.message.reply_text(
                "📅 Укажи свою дату рождения в формате ДД.ММ.ГГГГ:",
                reply_markup=ReplyKeyboardRemove()
            )
            return SET_BIRTHDAY
        else:
            await show_main_menu(update, context)
    return ConversationHandler.END

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=main_menu_keyboard()
    )

# Установка даты рождения
async def set_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    date_str = update.message.text.strip()
    
    if not is_valid_birthdate(date_str):
        await update.message.reply_text("❌ Некорректная дата. Попробуй снова (ДД.ММ.ГГГГ):")
        return SET_BIRTHDAY
    
    birthdays[str(user.id)] = {
        "date": date_str,
        "username": user.username or user.full_name
    }
    save_data(birthdays, BIRTHDAYS_FILE)
    
    await update.message.reply_text(
        "✅ Дата рождения сохранена!\n\n"
        "📝 Теперь давай создадим твой wish-лист. "
        "Отправь первую позицию для твоего списка желаний:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADD_WISHLIST_ITEM

# Добавление позиции в wish-лист
async def add_wishlist_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    item = censor_text(update.message.text.strip())
    
    # Инициализируем wish-лист, если его нет
    if user_id not in wishlists:
        wishlists[user_id] = []
    
    # Добавляем новую позицию
    wishlists[user_id].append(item)
    save_data(wishlists, WISHLISTS_FILE)
    
    # Предлагаем добавить еще или завершить
    await update.message.reply_text(
        f"✅ Позиция добавлена: {item}\n\n"
        "Отправь следующую позицию или нажми /done для завершения",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/done")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    return ADD_WISHLIST_ITEM

# Завершение создания wish-листа
async def finish_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    if user_id in wishlists and wishlists[user_id]:
        await update.message.reply_text(
            "🎉 Твой wish-лист создан!",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Ты не добавил ни одной позиции в wish-лист",
            reply_markup=main_menu_keyboard()
        )
    
    return ConversationHandler.END

# Просмотр wish-листа
async def view_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    if user_id in wishlists and wishlists[user_id]:
        wishlist_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(wishlists[user_id])])
        await update.message.reply_text(
            f"📝 Твой wish-лист:\n\n{wishlist_text}",
            reply_markup=main_menu_keyboard()
        )
        
        # Создаем и отправляем файл
        filename = f"wishlist_{user_id}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(wishlist_text)
        
        await update.message.reply_document(
            document=open(filename, "rb"),
            caption="Вот твой wish-лист в виде файла",
            reply_markup=main_menu_keyboard()
        )
        
        # Удаляем временный файл
        os.remove(filename)
    else:
        await update.message.reply_text(
            "❌ У тебя нет wish-листа. Нажми '✏️ Обновить wish-лист' чтобы создать",
            reply_markup=main_menu_keyboard()
        )

# Начало обновления wish-листа
async def update_wishlist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    # Если нет wish-листа, начинаем создание
    if user_id not in wishlists or not wishlists[user_id]:
        await update.message.reply_text(
            "📝 У тебя еще нет wish-листа. Отправь первую позицию:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_WISHLIST_ITEM
    
    # Показываем текущий wish-лист с кнопками для управления
    wishlist_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(wishlists[user_id])])
    
    # Создаем клавиатуру для управления
    keyboard = []
    for i in range(len(wishlists[user_id])):
        keyboard.append([KeyboardButton(f"❌ Удалить позицию {i+1}")])
    
    keyboard.append([KeyboardButton("➕ Добавить новую позицию")])
    keyboard.append([KeyboardButton("✅ Завершить обновление")])
    
    await update.message.reply_text(
        f"📝 Твой текущий wish-лист:\n\n{wishlist_text}\n\n"
        "Выбери действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    return UPDATE_WISHLIST

# Обновление wish-листа
async def update_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    item = censor_text(update.message.text.strip())
    
    # Инициализируем wish-лист, если его нет
    if user_id not in wishlists:
        wishlists[user_id] = []
    
    # Добавляем новую позицию
    wishlists[user_id].append(item)
    save_data(wishlists, WISHLISTS_FILE)
    
    await update.message.reply_text(
        f"✅ Позиция добавлена: {item}\n\n"
        "Отправь следующую позицию или нажми /done для завершения",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("/done")]],
            resize_keyboard=True
        )
    )
    return UPDATE_WISHLIST

# Обработка файлов wish-листа
async def handle_wishlist_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    
    # Получаем файл
    file = await update.message.document.get_file()
    await file.download_to_drive(f"wishlist_{user_id}_temp.txt")
    
    # Читаем содержимое файла
    try:
        with open(f"wishlist_{user_id}_temp.txt", "r", encoding="utf-8") as f:
            content = f.read().splitlines()
        
        # Фильтруем пустые строки
        items = [censor_text(line.strip()) for line in content if line.strip()]
        
        if items:
            wishlists[user_id] = items
            save_data(wishlists, WISHLISTS_FILE)
            
            # Форматируем для показа
            wishlist_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
            
            await update.message.reply_text(
                "✅ Wish-лист успешно обновлен из файла!\n\n"
                f"Твой новый wish-лист:\n\n{wishlist_text}",
                reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Файл не содержит данных. Попробуйте снова.",
                reply_markup=main_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка обработки файла: {e}")
        await update.message.reply_text(
            "❌ Ошибка обработки файла. Попробуйте другой формат.",
            reply_markup=main_menu_keyboard()
        )
    
    # Удаляем временный файл
    if os.path.exists(f"wishlist_{user_id}_temp.txt"):
        os.remove(f"wishlist_{user_id}_temp.txt")
    
    return ConversationHandler.END

async def delete_wishlist_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text
    
    # Извлекаем номер позиции из текста (пример: "❌ Удалить позицию 3")
    try:
        position = int(text.split()[-1]) - 1
        if 0 <= position < len(wishlists[user_id]):
            # Удаляем позицию
            removed_item = wishlists[user_id].pop(position)
            save_data(wishlists, WISHLISTS_FILE)
            
            await update.message.reply_text(
                f"✅ Позиция удалена: {removed_item}",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Неверный номер позиции",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Ошибка удаления позиции: {e}")
        await update.message.reply_text(
            "❌ Ошибка при удалении позиции",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
        
# Удаление wish-листа
async def delete_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    if user_id in wishlists:
        del wishlists[user_id]
        save_data(wishlists, WISHLISTS_FILE)
        await update.message.reply_text(
            "✅ Wish-лист удален!",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ У тебя нет wish-листа для удаления.",
            reply_markup=main_menu_keyboard()
        )

# Список дней рождений
async def all_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not birthdays:
        await update.message.reply_text(
            "❌ Дни рождения не добавлены.",
            reply_markup=main_menu_keyboard()
        )
        return
    
    text = "🎂 Дни рождения участников:\n\n"
    for user_id, data in birthdays.items():
        text += f"• {data['username']}: {data['date']}\n"
    
    await update.message.reply_text(
        text,
        reply_markup=main_menu_keyboard()
    )

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
                    user_id_str = str(user_id)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="🎁 Не забудь обновить свой wish-лист!",
                        reply_markup=main_menu_keyboard()
                    )
        except Exception as e:
            logger.error(f"Ошибка напоминания: {e}")

# Админские команды
async def admin_add_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        await update.message.reply_text("❌ Доступ запрещен!")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "Перешли сообщение пользователя и укажи дату в формате: ДД.ММ.ГГГГ"
    )
    return ADMIN_ADD_BIRTHDAY

async def admin_save_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Ошибка: нужно переслать сообщение!")
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
            await update.message.reply_text("❌ Некорректная дата!")
            return ADMIN_ADD_BIRTHDAY
        
        birthdays[user_id] = {
            "date": date_str,
            "username": user.username or user.full_name
        }
        save_data(birthdays, BIRTHDAYS_FILE)
        await update.message.reply_text("✅ Данные сохранены!")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    return ConversationHandler.END

# Новые участники группы
async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_CHAT_ID
    
    # Сохраняем ID группы при добавлении бота
    if context.bot.id in [user.id for user in update.message.new_chat_members]:
        GROUP_CHAT_ID = update.message.chat.id
        save_group_chat_id(GROUP_CHAT_ID)
        await update.message.reply_text(
            "🤖 Бот активирован! Напишите мне в ЛС /start для регистрации."
        )
        return
    
    # Приветствие новых участников
    for member in update.message.new_chat_members:
        if not member.is_bot:
            try:
                await context.bot.send_message(
                    chat_id=member.id,
                    text=WELCOME_MESSAGE,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение: {e}")
                await update.message.reply_text(
                    f"👋 {member.full_name}, напиши мне в ЛС /start для регистрации!"
                )

# Отмена операции
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Операция отменена",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# Обработчик текстовых сообщений (для меню)
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.message.from_user.id)
    
    if text == "🎁 Мой wish-лист":
        await view_wishlist(update, context)
    elif text == "✏️ Обновить wish-лист":
        await update_wishlist_start(update, context)
    elif text == "🗑️ Удалить wish-лист":
        await delete_wishlist(update, context)
    elif text == "📅 Все дни рождения":
        await all_birthdays(update, context)
    elif text == "👀 Wish-листы участников":
        await show_users_list(update, context)
    elif text.startswith("❌ Удалить позицию"):
        await delete_wishlist_item(update, context)
    elif text == "➕ Добавить новую позицию":
        await update.message.reply_text(
            "📝 Отправь новую позицию для wish-листа:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ADD_WISHLIST_ITEM
    elif text == "✅ Завершить обновление":
        await update.message.reply_text(
            "✅ Wish-лист обновлен!",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Используй меню для навигации",
            reply_markup=main_menu_keyboard()
        )

# Новая функция для показа списка участников
async def show_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not birthdays:
        await update.message.reply_text(
            "❌ Нет зарегистрированных участников",
            reply_markup=main_menu_keyboard()
        )
        return
    
    keyboard = []
    for user_id, data in birthdays.items():
        if user_id in wishlists and wishlists[user_id]:
            username = data['username']
            keyboard.append([KeyboardButton(f"👤 {username}")])
    
    if not keyboard:
        await update.message.reply_text(
            "❌ Нет участников с wish-листами",
            reply_markup=main_menu_keyboard()
        )
        return
    
    keyboard.append([KeyboardButton("🔙 Назад")])
    
    await update.message.reply_text(
        "Выбери участника для просмотра wish-листа:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    return VIEW_OTHERS_WISHLIST

# Функция для просмотра wish-листа другого участника
async def view_others_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text[2:]  # Убираем эмодзи "👤 "
    
    # Находим пользователя по username
    for user_id, data in birthdays.items():
        if data['username'] == username and user_id in wishlists and wishlists[user_id]:
            wishlist_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(wishlists[user_id])])
            
            await update.message.reply_text(
                f"🎁 Wish-лист пользователя {username}:\n\n{wishlist_text}",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END
    
    await update.message.reply_text(
        "❌ Wish-лист не найден",
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
            MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member),
            MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, menu_handler)
        ],
        states={
            SET_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_birthday),
                CommandHandler("cancel", cancel)
            ],
            ADD_WISHLIST_ITEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_wishlist_item),
                CommandHandler("done", finish_wishlist),
                CommandHandler("cancel", cancel),
                MessageHandler(filters.Document.TXT, handle_wishlist_file)
            ],
            UPDATE_WISHLIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler),  # Обработка через menu_handler
                CommandHandler("cancel", cancel)
            ],
            ADMIN_ADD_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_save_birthday),
                CommandHandler("cancel", cancel)
            ],
            VIEW_OTHERS_WISHLIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, view_others_wishlist),
                CommandHandler("cancel", cancel)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Регистрация обработчиков
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("admin_add", admin_add_birthday))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, menu_handler))
    app.add_handler(MessageHandler(filters.Document.TXT & filters.ChatType.PRIVATE, handle_wishlist_file))
    
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
