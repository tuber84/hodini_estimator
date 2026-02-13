import asyncio
from telegram import Bot

async def send_message():
    # Замените 'YOUR_BOT_TOKEN' на токен вашего бота
    bot_token = '7436817905:AAHbjbDKNJMQ_fHZ61c7IfeMk6aZT6ZnjUg'
    # Замените 'YOUR_CHANNEL_ID' на ID вашего канала (например, '@your_channel_name')
    channel_id = '-1002174266719'
    message = 'Привет, это сообщение от моего бота!'

    # Создаем экземпляр бота
    bot = Bot(token=bot_token)

    # Отправляем сообщение
    await bot.send_message(chat_id=channel_id, text=message)

# Запускаем асинхронную функцию
asyncio.run(send_message())