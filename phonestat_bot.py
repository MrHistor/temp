import os
import re
import zipfile
import tempfile
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Функция для получения токена из файла
def get_token() -> str:
    try:
        with open("token.txt", "r") as token_file:
            token = token_file.read().strip()
            if not token:
                raise ValueError("Файл token.txt пустой")
            return token
    except FileNotFoundError:
        print("❌ Файл token.txt не найден")
        raise
    except Exception as e:
        print(f"❌ Ошибка при чтении token.txt: {str(e)}")
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🔋 Battery Log Analyzer Bot\n\n"
        "Отправьте мне:\n"
        "1. ZIP-архив с логом (содержащий bugreport*.txt)\n"
        "2. TXT-файл с названием bugreport*.txt\n\n"
        "Я извлеку данные о батарее (fc и cc)"
    )
    await update.message.reply_text(text)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Получаем информацию о файле
    document = update.message.document
    file_name = document.file_name.lower()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            # Скачиваем файл
            file = await document.get_file()
            file_path = os.path.join(tmp_dir, file_name)
            await file.download_to_drive(file_path)
            
            # Обработка ZIP
            if file_name.endswith(".zip"):
                result = await process_zip(file_path, tmp_dir)
            # Обработка TXT
            elif "bugreport" in file_name and file_name.endswith(".txt"):
                result = await process_txt(file_path)
            else:
                result = "❌ Неподдерживаемый формат. Нужен ZIP или TXT (bugreport*.txt)"
            
            await update.message.reply_text(result)
        
        except Exception as e:
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

async def process_zip(zip_path: str, tmp_dir: str) -> str:
    # Создаем отдельную папку для распаковки
    extract_dir = os.path.join(tmp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    
    # Распаковка архива
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    # Поиск txt-файлов
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().startswith("bugreport") and file.lower().endswith(".txt"):
                return await process_txt(os.path.join(root, file))
    
    return "❌ В архиве не найден файл bugreport*.txt"

async def process_txt(file_path: str) -> str:
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
                        # Не прерываем поиск, чтобы найти последнее вхождение
    
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
    try:
        token = get_token()
    except Exception as e:
        print(f"❌ Не удалось запустить бота: {str(e)}")
        print("Создайте файл token.txt с токеном бота")
        return

    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
