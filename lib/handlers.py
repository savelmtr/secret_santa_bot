from lib.viewmodel import (create_room, get_max_price, set_max_price,
                        get_user, get_user_info, lock, enlock,
                        set_user_name_data, set_wishes, rename_room,
                       to_room_attach)
from lib.states import States
from lib.base import CustomBot
from lib.callback_texts import CALLBACK_TEXTS
from telebot.types import Message, InlineKeyboardButton, InlineKeyboardMarkup


async def try_rename_room(message: Message, data, bot: CustomBot):
    rename_msg = await rename_room(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, rename_msg)


async def get_room(message: Message, data, bot: CustomBot):
    payload = message.text[6:].strip()
    if not payload:
        create_room_btn = InlineKeyboardButton(text='Создать комнату', callback_data='create_room')
        connect_room_btn = InlineKeyboardButton(text='Подключиться к комнате', callback_data='connect_room')
        markup = InlineKeyboardMarkup()
        markup.add(create_room_btn)
        markup.add(connect_room_btn)
        await bot.reply_to(message, CALLBACK_TEXTS.welcome, reply_markup=markup)
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


async def enter_max_price(message: Message, data, bot: CustomBot):
    price_message = await set_max_price(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, price_message)


async def get_user_wishes(message: Message, data, bot: CustomBot):
    payload = message.text
    if not payload:
        await bot.set_state(message.from_user.id, States.wish_list, message.chat.id)
    else:
        await set_wishes(message.from_user.id, payload)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user)
    await bot.reply_to(message, msg)


async def get_user_name(message: Message, data, bot: CustomBot):
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


async def entering_to_room(message: Message, data, bot: CustomBot):
    enlocked = await enlock(message.from_user, message.text)
    if enlocked:
        await bot.send_message(message.chat.id, 'Комната открыта 🔓')
        await bot.delete_state(message.from_user.id, message.chat.id)
    else:
        await bot.send_message(message.chat.id, 'Пароль не подходит 😞 Попробуйте еще раз')
        await bot.set_state(message.from_user.id, States.enter_password, message.chat.id)


async def connect_room(message: Message, data, bot: CustomBot):
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


async def create_password_handler(message: Message, data, bot: CustomBot):
    lock_msg = await lock(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, lock_msg)


async def callback_query(call, data, bot: CustomBot):
    req = call.data
    if 'create_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text='Введите название комнаты')
        await bot.set_state(call.from_user.id, States.create_room, call.message.chat.id)
    elif 'connect_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text=CALLBACK_TEXTS.connection_room)
        await bot.delete_state(call.from_user.id, call.message.chat.id)
        await bot.set_state(call.from_user.id, States.connect_room, call.message.chat.id)


async def create_room_handler(message: Message, data, bot: CustomBot):
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


async def update_name(message: Message, data, bot: CustomBot):
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


async def update_wishes(message: Message, data, bot: CustomBot):
    wishes = message.text
    await set_wishes(message.from_user.id, wishes)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    await bot.reply_to(message, msg)
