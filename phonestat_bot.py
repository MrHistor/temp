import os
import re
import zipfile
import tempfile
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Конфигурация
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замените на ваш токен

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start с клавиатурой"""
    keyboard = [
        [KeyboardButton("📤 Отправить файл")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    text = (
        "🔋 Battery Log Analyzer Bot\n\n"
        "Отправьте мне:\n"
        "1. ZIP-архив с логом (содержащий bugreport*.txt)\n"
        "2. TXT-файл с названием bugreport*.txt\n\n"
        "Я извлеку данные о батарее (fc и cc)"
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик загруженных файлов"""
    # Создаем временную директорию
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            # Скачиваем файл
            file = await update.message.document.get_file()
            file_path = os.path.join(tmp_dir, "file")
            await file.download_to_drive(file_path)
            
            # Обработка ZIP
            if file_path.endswith(".zip"):
                result = await process_zip(file_path, tmp_dir)
            # Обработка TXT
            elif file_path.endswith(".txt") and "bugreport" in file_path.lower():
                result = await process_txt(file_path)
            else:
                result = "❌ Неподдерживаемый формат. Нужен ZIP или TXT (bugreport*.txt)"
            
            await update.message.reply_text(result)
        
        except Exception as e:
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

async def process_zip(zip_path: str, tmp_dir: str) -> str:
    """Обработка ZIP-архива"""
    # Распаковка архива
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(tmp_dir)
    
    # Поиск txt-файлов
    for root, _, files in os.walk(tmp_dir):
        for file in files:
            if file.startswith("bugreport") and file.endswith(".txt"):
                return await process_txt(os.path.join(root, file))
    
    return "❌ В архиве не найден файл bugreport*.txt"

async def process_txt(file_path: str) -> str:
    """Построчная обработка TXT-файла"""
    fc_value = cc_value = None
    pattern = re.compile(r'healthd.*?fc=(\d+).*?cc=(\d+)')
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if "healthd" in line:
                    match = pattern.search(line)
                    if match:
                        fc_value = match.group(1)
                        cc_value = match.group(2)
    
    except Exception as e:
        return f"⚠️ Ошибка чтения файла: {str(e)}"
    
    if fc_value and cc_value:
        return (
            f"🔋 Результат анализа:\n\n"
            f"• Capacity (fc) = {fc_value}\n"
            f"• Cycles (cc) = {cc_value}"
        )
    return "❌ Данные о батарее не найдены"

def main() -> None:
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("📤 Отправить файл"), handle_file))
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
