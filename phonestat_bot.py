import os
import re
import zipfile
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

# Функция для извлечения информации из лог-файла
def parse_log_file(file):
    data = {
        "capacity": "Не найдено",
        "cycles": "Не найдено",
        "build": "Не найдено",
        "ram": "Не найдено",
        "rom": "Не найдено",
        "accounts": []
    }
    
    # Регулярные выражения для поиска данных
    patterns = {
        "healthd": re.compile(r'healthd:.*fc=(\d+).*cc=(\d+)'),
        "build": re.compile(r'Build:\s*([^\s]+)'),
        "ram": re.compile(r'androidboot\.hardware\.ddr\s*=\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"'),
        "rom": re.compile(r'androidboot\.hardware\.ufs\s*=\s*"([^"]+)"\s*,\s*"([^"]+)"'),
        "account": re.compile(r'Account\s*\{name=([^,]+?),\s*type=([^\}]+?)\}')
    }

    # Множество для отслеживания уникальных аккаунтов
    seen_accounts = set()

    # Построчная обработка файла
    for line in file:
        try:
            # Декодирование с обработкой ошибок
            line_str = line.decode('utf-8', errors='ignore')
        except AttributeError:
            line_str = line
            
        # Поиск данных в строке
        if "healthd" in line_str and data["capacity"] == "Не найдено":
            match = patterns["healthd"].search(line_str)
            if match:
                capacity = match.group(1)
                # Удаляем три нуля с конца и добавляем mAh
                if capacity.endswith('000'):
                    capacity = capacity[:-3] + "mAh"
                else:
                    capacity += "mAh"
                data["capacity"] = capacity
                data["cycles"] = match.group(2)
                
        elif "Build:" in line_str and data["build"] == "Не найдено":
            match = patterns["build"].search(line_str)
            if match:
                data["build"] = match.group(1)
                
        elif "androidboot.hardware.ddr" in line_str and data["ram"] == "Не найдено":
            match = patterns["ram"].search(line_str)
            if match:
                data["ram"] = f"{match.group(1)}, {match.group(2)}, {match.group(3)}"
                
        elif "androidboot.hardware.ufs" in line_str and data["rom"] == "Не найдено":
            match = patterns["rom"].search(line_str)
            if match:
                data["rom"] = f"{match.group(1)}, {match.group(2)}"
                
        elif "Account {" in line_str:
            match = patterns["account"].search(line_str)
            if match:
                account_name = match.group(1).strip()
                account_type = match.group(2).strip()
                
                # Фильтрация аккаунтов по наличию '@' и удаление дубликатов
                if '@' in account_name:
                    account_id = f"{account_name.lower()}|{account_type.lower()}"
                    if account_id not in seen_accounts:
                        seen_accounts.add(account_id)
                        data["accounts"].append((account_name, account_type))
                
    return data

# Форматирование результатов
def format_results(data):
    accounts = "\n".join([f"• {name} ({type})" for name, type in data["accounts"]]) or "Не найдено"
    
    return (
        "🔍 Результаты анализа лога:\n\n"
        f"🔋 Остаточная емкость батареи: {data['capacity']}\n"
        f"🔄 Циклы заряда: {data['cycles']}\n"
        f"📱 Build: {data['build']}\n"
        f"💾 RAM: {data['ram']}\n"
        f"💽 ROM: {data['rom']}\n\n"
        f"👥 Аккаунты:\n{accounts}"
    )

# Обработчик команды /start
async def start(update: Update, context):
    keyboard = [[InlineKeyboardButton("📖 Показать инструкцию", callback_data='instruction')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "Привет! Я помогу проанализировать Bug Report твоего Android-устройства.\n\n"
        "Я покажу информацию о:\n"
        "- Батарее (емкость и циклы заряда)\n"
        "- Номер сборки\n"
        "- Характеристиках RAM и ROM\n"
        "- Привязанных аккаунтах\n\n"
        "Просто отправь мне ZIP-файл с логом!"
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup
    )

# Обработчик инструкции
async def show_instruction(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    instruction = (
        "Как сделать Bug Report на Android:\n\n"
        "1. Откройте 'Настройки' > 'О телефоне'\n"
        "2. Нажмите 7 раз на 'Номер сборки' для разблокировки режима разработчика\n"
        "3. Вернитесь в 'Настройки' > 'Система' > 'Для разработчиков'\n"
        "4. Активируйте 'Отчет об ошибках'\n"
        "5. Создайте отчет через меню питания (кнопка питания + Volume Down)\n"
        "6. Дождитесь создания отчета (может занять несколько минут)\n"
        "7. Поделитесь ZIP-файлом через Telegram"
    )
    
    await query.edit_message_text(
        text=instruction,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data='back')]])
    )

# Возврат к главному меню
async def back_to_main(update: Update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text= (
        "Я помогу проанализировать Bug Report твоего Android-устройства.\n\n"
        "Я покажу информацию о:\n"
        "- Батарее (емкость и циклы заряда)\n"
        "- Номер сборки\n"
        "- Характеристиках RAM и ROM\n"
        "- Привязанных аккаунтах\n\n"
        "Отправь мне ZIP-файл с логом Android для анализа."
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 Показать инструкцию", callback_data='instruction')]])
    )

# Обработчик ZIP-файлов
async def handle_zip(update: Update, context):
    message = update.message
    document = message.document
    
    if not document.file_name.endswith('.zip'):
        await message.reply_text("❌ Пожалуйста, отправьте ZIP-файл.")
        return
        
    # Скачивание файла
    file = await context.bot.get_file(document)
    file_stream = io.BytesIO()
    await file.download_to_memory(file_stream)
    file_stream.seek(0)
    
    try:
        # Обработка ZIP-архива
        with zipfile.ZipFile(file_stream) as z:
            # Ищем лог-файл в корне и поддиректориях
            log_files = []
            for file_info in z.infolist():
                if "bugreport" in file_info.filename and file_info.filename.endswith('.txt'):
                    log_files.append(file_info.filename)
            
            if not log_files:
                await message.reply_text("❌ Файл лога bugreport*.txt не найден в архиве.")
                return
                
            # Берём первый найденный лог-файл
            with z.open(log_files[0]) as log_file:
                data = parse_log_file(log_file)
                result = format_results(data)
                await message.reply_text(result)
                
    except Exception as e:
        await message.reply_text(f"⛔ Ошибка обработки файла: {str(e)}")

# Основная функция
def main():
    # Загрузка токена из файла
    with open('token.txt') as f:
        token = f.read().strip()
    
    app = Application.builder().token(token).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_zip))
    app.add_handler(CallbackQueryHandler(show_instruction, pattern='instruction'))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern='back'))
    
    app.run_polling()

if __name__ == '__main__':
    main()
