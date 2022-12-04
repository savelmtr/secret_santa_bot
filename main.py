import asyncio
import os

from telebot import asyncio_filters, types
from telebot.asyncio_storage import StateMemoryStorage
from telebot.types import Message

from lib.callback_texts import CALLBACK_TEXTS
from lib.viewmodel import (create_room, get_max_price, set_max_price,
                        get_user, get_user_info, lock, enlock,
                        set_user_name_data, set_wishes, rename_room,
                       to_room_attach)
from lib.states import States
from lib.buttons import AdminButtonSet, UserButtonSet
from lib.base import CustomBot


TOKEN = os.getenv('TOKEN')

bot = CustomBot(TOKEN, state_storage=StateMemoryStorage())
bot.add_button_set(AdminButtonSet)
bot.add_button_set(UserButtonSet)
bot.add_custom_filter(asyncio_filters.StateFilter(bot))


@bot.message_handler(state=States.update_name)
async def update_name(message):
    name_data = str(message.text).split(' ')
    if len(name_data) != 2:
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова 😀')
        await bot.set_state(message.from_user.id, States.user_name, message.chat.id)
    first_name, last_name = name_data
    if not str(first_name).isalpha() or not str(last_name).isalpha():
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова используя только буквы 😀')
        await bot.set_state(message.from_user.id, States.user_name, message.chat.id)
    await set_user_name_data(first_name, last_name, message.from_user)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    await bot.reply_to(message, msg)


@bot.message_handler(state=States.update_wishes)
async def update_wishes(message):
    wishes = message.text
    await set_wishes(message.from_user.id, wishes)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    await bot.reply_to(message, msg)


@bot.message_handler(commands=['help'])
async def send_welcome(message, markup):
    await bot.reply_to(message, CALLBACK_TEXTS.welcome, reply_markup=markup)


@bot.message_handler(state=States.create_room)
async def create_room_(message):
    room_name = message.text
    room_id = await create_room(room_name, message.from_user)
    await bot.reply_to(message, f'Вы создали комнату {room_name} c id {room_id}')
    bot_info = await bot.get_me()
    await bot.send_message(message.chat.id, CALLBACK_TEXTS.link.format(room_name=room_name,
                                                                       bot_name=bot_info.username,
                                                                       room_id=room_id))

    msg = await get_user_info(message.from_user)
    await bot.send_message(message.chat.id, f'Вы успешно создали комнату {room_name}!\n'
                                            'Ваши данные:\n'
                                            f'{msg}')
    await bot.delete_state(message.from_user.id, message.chat.id)


@bot.callback_query_handler(func=lambda call: 'room' in call.data)
async def callback_query(call):
    req = call.data
    if 'create_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text='Введите название комнаты')
        await bot.set_state(call.from_user.id, States.create_room, call.message.chat.id)
    elif 'connect_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text=CALLBACK_TEXTS.connection_room)
        await bot.delete_state(call.from_user.id, call.message.chat.id)
        await bot.set_state(call.from_user.id, States.connect_room, call.message.chat.id)


@bot.message_handler(state=States.create_password)
async def create_password_(message: Message):
    lock_msg = await lock(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, lock_msg)


@bot.message_handler(state=States.connect_room)
async def connect_room_(message: Message):
    try:
        room_id = int(message.text)
    except ValueError:
        await bot.reply_to(message, f'Не найдено комнаты c id:{message.text}! Попробуйте еще раз!')
        return
    room_name, is_protected = await to_room_attach(room_id, message.from_user)
    if not room_name:
        await bot.reply_to(message, f'Не найдено комнаты c id:{room_id}! Попробуйте еще раз!')
        await bot.set_state(message.from_user.id, States.connect_room, message.chat.id)
    elif room_name and not is_protected:
        await bot.reply_to(message, CALLBACK_TEXTS.connect_to_room.format(room_name=room_name))
        await bot.set_state(message.from_user.id, States.user_name, message.chat.id)

    elif room_name and is_protected:
        await bot.reply_to(
            message,
            f'Хо-хоу-хоу!'
            f'Вы присоединились к комнате {room_name} c id:{room_id}.'
            ' Комната заперта, введите пожалуйста пароль'
        )
        await bot.set_state(message.from_user.id, States.enter_password, message.chat.id)


@bot.message_handler(state=States.enter_password)
async def entering_to_room(message):
    enlocked = await enlock(message.from_user, message.text)
    if enlocked:
        await bot.send_message(message.chat.id, 'Комната открыта 🔓', reply_markup=markup)
        await bot.delete_state(message.from_user.id, message.chat.id)
    else:
        await bot.send_message(message.chat.id, 'Пароль не подходит 😞 Попробуйте еще раз')
        await bot.set_state(message.from_user.id, States.enter_password, message.chat.id)


@bot.message_handler(state=States.user_name)
async def get_user_name(message: Message):
    name_data = str(message.text).split(' ')
    if len(name_data) != 2:
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова 😀')
        await bot.set_state(message.from_user.id, States.user_name, message.chat.id)
    first_name, last_name = name_data
    if not str(first_name).isalpha() or not str(last_name).isalpha():
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова используя только буквы 😀')
        await bot.set_state(message.from_user.id, States.user_name, message.chat.id)
    await set_user_name_data(first_name, last_name, message.from_user)
    price = await get_max_price(message.from_user.id)
    await bot.send_message(message.chat.id, CALLBACK_TEXTS.wish_message.format(max_price=price))
    await bot.set_state(message.from_user.id, States.wish_list, message.chat.id)


@bot.message_handler(state=States.wish_list)
async def get_user_wishes(message: Message):
    payload = message.text
    if not payload:
        await bot.set_state(message.from_user.id, States.wish_list, message.chat.id)
    else:
        await set_wishes(message.from_user.id, payload)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user)
    await bot.reply_to(message, msg)


@bot.message_handler(state=States.max_price)
async def enter_max_price(message):
    price_message = await set_max_price(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, price_message)


@bot.message_handler(commands=['start'])
async def get_room(message: Message):
    payload = message.text[6:].strip()
    if not payload:
        create_room_btn = types.InlineKeyboardButton(text='Создать комнату', callback_data='create_room')
        connect_room_btn = types.InlineKeyboardButton(text='Подключиться к комнате', callback_data='connect_room')
        markup = types.InlineKeyboardMarkup()
        markup.add(create_room_btn)
        markup.add(connect_room_btn)
        await send_welcome(message, markup)
    else:
        user = await get_user(message.from_user)
        try:
            in_room = int(payload) == user.room_id
        except ValueError:
            await bot.send_message(message.chat.id, f'"{payload}" не является валидным id комнаты')
            return
        if not in_room:
            room_name, is_protected = await to_room_attach(int(payload), message.from_user)
            if is_protected:
                await bot.send_message(message.chat.id, 'Ох-хоу-хоу 🎅'
                                                        f'Похоже комната  {room_name} запоролена.'
                                                        f'Введите пожалуйста пароль')
                await bot.set_state(user.id, States.enter_password, message.chat.id)
            else:
                await bot.reply_to(message, CALLBACK_TEXTS.connect_to_room.format(room_name=room_name))
                await bot.set_state(user.id, States.user_name, message.chat.id)
        else:
            await bot.send_message(message.chat.id, 'Хо-хо-хо! Вы вернулись!')


@bot.message_handler(state=States.rename)
async def try_rename_room(message):
    rename_msg = await rename_room(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, rename_msg)


if __name__ == '__main__':
    asyncio.run(bot.polling())
