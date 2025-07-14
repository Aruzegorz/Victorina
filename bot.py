import logging
import os
from telegram import Update, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# НАСТРОЙКИ БОТА
# Замените на ваш токен от BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# URL вашего веб-приложения 
# Для локальной разработки через ngrok: "https://abc123.ngrok.io"
# Для продакшена через Render: "https://your-app-name.onrender.com"
WEB_APP_URL = "YOUR_WEB_APP_URL_HERE"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - показывает главное меню с кнопкой Mini App"""
    
    # Создаем кнопку с Web App
    web_app = WebAppInfo(url=WEB_APP_URL)
    keyboard = [
        [KeyboardButton("🧠 Открыть викторину", web_app=web_app)],
        [KeyboardButton("ℹ️ Помощь"), KeyboardButton("📊 О боте")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    user_name = update.effective_user.first_name
    welcome_text = f"""
🎉 *Привет, {user_name}! Добро пожаловать в умную викторину!*

🧠 *Что вас ждет:*
• 📚 История - проверьте знания прошлого
• 🔬 Наука - разгадайте тайны природы  
• 🌍 Общие знания - покажите эрудицию

✨ *Особенности:*
• Красивый современный интерфейс
• Мгновенная проверка ответов
• Таблица рекордов среди всех игроков
• Отслеживание вашего прогресса

🎯 *Готовы проверить свои знания?*
Нажмите кнопку ниже, чтобы начать игру!
"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - показывает подробную помощь"""
    
    help_text = """
🆘 *Подробная помощь по викторине*

🎮 *Как играть:*
1️⃣ Нажмите кнопку '🧠 Открыть викторину'
2️⃣ Выберите одну из трех категорий
3️⃣ Отвечайте на вопросы, нажимая на варианты ответов
4️⃣ Смотрите результат после каждого ответа
5️⃣ Получите финальную оценку в конце

🏆 *Категории вопросов:*
• 🏛 *История* - события прошлого, великие личности, даты
• 🔬 *Наука* - физика, химия, биология, открытия
• 🌍 *Общие знания* - география, спорт, культура

📊 *Система оценок:*
• 🏆 80-100% = Отлично! Вы эрудит!
• 🥉 60-79% = Хорошо! Продолжайте в том же духе!
• 📚 40-59% = Неплохо! Есть к чему стремиться!
• 💪 0-39% = Не расстраивайтесь, учитесь дальше!

🎯 *Полезные советы:*
• Читайте вопросы внимательно
• Не торопитесь с ответом
• Изучайте правильные ответы
• Играйте в разных категориях
• Соревнуйтесь с друзьями!

🔄 *Можете играть сколько угодно раз и улучшать свои результаты!*
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о боте"""
    
    about_text = """
🤖 *О викторине*

📱 *Это Telegram Mini App* - современное веб-приложение, которое работает прямо в Telegram без установки дополнительных программ.

👨‍💻 *Технологии:*
• Python + Flask (серверная часть)
• HTML5 + CSS3 + JavaScript (интерфейс)
• SQLite (база данных для рекордов)
• Telegram Bot API + Mini Apps

🎯 *Цели проекта:*
• Обучение и развлечение
• Проверка эрудиции
• Изучение новых фактов
• Соревнование с друзьями

📈 *Статистика сохраняется:*
• Ваши лучшие результаты по каждой категории
• Общая таблица лидеров
• История всех игр

🚀 *Постоянное развитие:*
Мы регулярно добавляем новые вопросы и улучшаем интерфейс!

💬 *Есть вопросы или предложения?*
Пишите разработчику через /help
"""
    
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    
    text = update.message.text.lower()
    
    if "помощь" in text or text == "ℹ️ помощь":
        await help_command(update, context)
    elif "о боте" in text or text == "📊 о боте":
        await about_command(update, context)
    elif "викторин" in text or "игр" in text:
        await update.message.reply_text(
            "🎮 Для начала игры нажмите кнопку '🧠 Открыть викторину' в меню!"
        )
    elif "привет" in text or "hello" in text:
        await update.message.reply_text(
            f"👋 Привет, {update.effective_user.first_name}! "
            "Готовы проверить свои знания? Нажмите '🧠 Открыть викторину'!"
        )
    else:
        await update.message.reply_text(
            "🤔 Не понял команду. Используйте:\n"
            "• /start - главное меню\n"
            "• /help - помощь\n"
            "• '🧠 Открыть викторину' - начать игру"
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ошибок"""
    logger.warning(f'Update {update} caused error {context.error}')

def main():
    """Запуск бота"""
    
    # Проверяем настройки
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Необходимо заменить YOUR_BOT_TOKEN_HERE на ваш токен от BotFather!")
        return
    
    if WEB_APP_URL == "YOUR_WEB_APP_URL_HERE":
        print("❌ ОШИБКА: Необходимо заменить YOUR_WEB_APP_URL_HERE на URL вашего приложения!")
        return
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    print("🤖 Бот запускается...")
    print(f"🌐 Web App URL: {WEB_APP_URL}")
    print("📱 Mini App готов к работе!")
    print("✨ Найдите вашего бота в Telegram и отправьте /start")
    
    # Запуск polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

