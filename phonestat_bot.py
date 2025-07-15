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
        "display_id": "Не найдено",
        "resolution": "Не найдено",
        "dpi": "Не найдено",
        "refresh_rates": "Не найдено",
        "manufacturer": "Не найдено",
        "manufacture_date": "Не найдено",
        "brightness": "Не найдено",
        "battery_health": "Не найдено",
        "accounts": []
    }
    
    # Регулярные выражения для поиска данных
    patterns = {
        "healthd": re.compile(r'healthd:.*fc=(\d+).*cc=(\d+)'),
        "build": re.compile(r'Build:\s*([^\s]+)'),
        "ram": re.compile(r'androidboot\.hardware\.ddr\s*=\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"'),
        "rom": re.compile(r'androidboot\.hardware\.ufs\s*=\s*"([^"]+)"\s*,\s*"([^"]+)"'),
        "display_id": re.compile(r'mPhysicalDisplayId=(\d+)'),
        "resolution": re.compile(r'mActiveSfDisplayMode=.*?width=(\d+), height=(\d+)'),
        "dpi": re.compile(r'mActiveSfDisplayMode=.*?xDpi=([\d.]+), yDpi=([\d.]+)'),
        "refresh_rates": re.compile(r'mSupportedRefreshRates=\[([\d\., ]+)\]'),
        "manufacturer": re.compile(r'manufacturerPnpId=(\w+)'),
        "manufacture_date": re.compile(r'ManufactureDate\{week=(\d+), year=(\d+)\}'),
        "brightness": re.compile(r'mNits=\[([\d\., ]+)\]'),
        "battery_drain": re.compile(r'mDreamsBatteryLevelDrain=(-?\d+)'),
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
        
        elif "mDreamsBatteryLevelDrain" in line_str and data["battery_health"] == "Не найдено":
            match = patterns["battery_drain"].search(line_str)
            if match:
                drain = int(match.group(1))
                health = 100 - drain
                data["battery_health"] = f"{health}%"
                
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
        
        elif "mPhysicalDisplayId" in line_str and data["display_id"] == "Не найдено":
            match = patterns["display_id"].search(line_str)
            if match:
                data["display_id"] = match.group(1)
                
        elif "mActiveSfDisplayMode" in line_str and data["resolution"] == "Не найдено":
            match_res = patterns["resolution"].search(line_str)
            match_dpi = patterns["dpi"].search(line_str)
            
            if match_res:
                data["resolution"] = f"{match_res.group(1)}x{match_res.group(2)}"
                
            if match_dpi:
                x_dpi = float(match_dpi.group(1))
                y_dpi = float(match_dpi.group(2))
                # Рассчет DPI по формуле √(xDpi^2 + yDpi^2)
                dpi_value = round((x_dpi**2 + y_dpi**2)**0.5)
                data["dpi"] = str(dpi_value)
                
        elif "mSupportedRefreshRates" in line_str and data["refresh_rates"] == "Не найдено":
            match = patterns["refresh_rates"].search(line_str)
            if match:
                rates = [rate.strip() for rate in match.group(1).split(',')]
                # Фильтрация уникальных частот и преобразование в целые
                unique_rates = []
                for rate in rates:
                    try:
                        # Преобразование в float и округление до целого
                        rate_value = str(int(float(rate)))
                        if rate_value not in unique_rates:
                            unique_rates.append(rate_value)
                    except ValueError:
                        continue
                data["refresh_rates"] = ", ".join(unique_rates) + " Hz"
                
        elif "manufacturerPnpId" in line_str and data["manufacturer"] == "Не найдено":
            match = patterns["manufacturer"].search(line_str)
            if match:
                data["manufacturer"] = match.group(1)
                
        elif "ManufactureDate" in line_str and data["manufacture_date"] == "Не найдено":
            match = patterns["manufacture_date"].search(line_str)
            if match:
                data["manufacture_date"] = f"{match.group(2)} г."
                
        elif "mNits" in line_str and data["brightness"] == "Не найдено":
            match = patterns["brightness"].search(line_str)
            if match:
                nits = [float(nit.strip()) for nit in match.group(1).split(',')]
                if nits:
                    # Берем максимальное значение яркости
                    max_brightness = max(nits)
                    data["brightness"] = f"{int(max_brightness)} Nit"
                
    return data

# Форматирование результатов
def format_results(data):
    accounts = "\n".join([f"• {name} ({type})" for name, type in data["accounts"]]) or "Не найдено"
    battery_info = f"• Остаточная емкость: {data['capacity']}"
    if data["battery_health"] != "Не найдено":
        battery_info += f" ({data['battery_health']})"
    battery_info += "\n"
    
    return (
        "🔍 Результаты анализа лога:\n\n"
        "🔋 Батарея:\n"
        f"{battery_info}"
        f"• Циклы заряда: {data['cycles']}\n\n"
        #📱💾💽
        f"Build: {data['build']}\n\n"
        f"RAM: {data['ram']}\n\n"
        f"ROM: {data['rom']}\n\n"
        "🖥️ Дисплей:\n"
        f"• ID: {data['display_id']}\n"
        f"• Разрешение: {data['resolution']}\n"
        f"• DPI: {data['dpi']}\n"
        f"• Частота обновления: {data['refresh_rates']}\n"
        f"• Производитель: {data['manufacturer']}\n"
        f"• Дата производства: {data['manufacture_date']}\n"
        f"• Максимальная яркость: {data['brightness']}\n\n"
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
        "- Параметрах дисплея (разрешение, DPI, яркость)\n"
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
        "- Параметрах дисплея (разрешение, DPI, яркость)\n"
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
