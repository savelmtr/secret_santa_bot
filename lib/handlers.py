from lib.viewmodel import (create_room, set_max_price,
                        get_user, get_user_info, lock, enlock,
                        set_user_name_data, set_wishes, rename_room,
                       to_room_attach)
from lib.states import States
from lib.base import CustomBot
from lib.callback_texts import CALLBACK_TEXTS
from telebot.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from lib.buttons import ChangeWishes, ChangeMyName


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
            room_id = int(payload)
        except ValueError:
            await bot.send_message(message.chat.id, CALLBACK_TEXTS.room_id_incorrect.format(payload=payload))
            return
        if not room_id == user.room_id:
            await connect_room_helper(message, room_id, bot)
        else:
            await bot.send_message(message.chat.id, 'Хо-хо-хо! Вы вернулись!')


async def enter_max_price(message: Message, data, bot: CustomBot):
    price_message = await set_max_price(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, price_message)


async def update_wishes(message: Message, data, bot: CustomBot):
    wishes = message.text
    await set_wishes(message.from_user.id, wishes)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    await bot.reply_to(message, msg)


async def update_name(message: Message, data, bot: CustomBot):
    name_data = str(message.text).split(' ', 1)
    first_name, last_name = (name_data + [''])[:2]
    if not first_name.isalpha() or (not last_name.isalpha() and last_name):
        await bot.reply_to(message, 'Назовите себя, используя только буквы 😀')
        await bot.set_state(message.from_user.id, States.user_name, message.chat.id)
    await set_user_name_data(first_name, last_name, message.from_user)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    await bot.reply_to(message, msg)


async def entering_to_room(message: Message, data, bot: CustomBot):
    enlocked = await enlock(message.from_user, message.text)
    if enlocked:
        markup = get_name_wishes_markup()
        await bot.send_message(message.chat.id, CALLBACK_TEXTS.enlock_room, reply_markup=markup)
        await bot.delete_state(message.from_user.id, message.chat.id)
    else:
        await bot.send_message(message.chat.id, 'Пароль не подходит 😞 Попробуйте еще раз')
        await bot.set_state(message.from_user.id, States.enter_password, message.chat.id)


def get_name_wishes_markup():
    change_name_btn = InlineKeyboardButton(text='Как меня зовут', callback_data='change_name')
    set_wishes_btn = InlineKeyboardButton(text='Что я хочу в подарок', callback_data='set_wishes')
    markup = InlineKeyboardMarkup()
    markup.add(change_name_btn)
    markup.add(set_wishes_btn)
    return markup


async def connect_room_helper(message: Message, room_id: int, bot):
    room_name, is_protected = await to_room_attach(room_id, message.from_user)
    if not room_name:
        await bot.reply_to(message, CALLBACK_TEXTS.room_id_not_found.format(room_id=room_id))
        await bot.set_state(message.from_user.id, States.connect_room, message.chat.id)
    elif room_name and not is_protected:
        markup = get_name_wishes_markup()
        await bot.send_message(
            message.chat.id,
            CALLBACK_TEXTS.connect_to_room.format(room_name=room_name),
            reply_markup=markup
        )
        await bot.delete_state(message.from_user.id, message.chat.id)
    elif room_name and is_protected:
        await bot.reply_to(
            message,
            CALLBACK_TEXTS.password_required.format(room_name=room_name, room_id=room_id)
        )
        await bot.set_state(message.from_user.id, States.enter_password, message.chat.id)


async def connect_room(message: Message, data, bot: CustomBot):
    try:
        room_id = int(message.text)
    except ValueError:
        await bot.reply_to(message, CALLBACK_TEXTS.room_id_incorrect.format(payload=message.text))
        return
    await connect_room_helper(message, room_id, bot)


async def create_password_handler(message: Message, data, bot: CustomBot):
    lock_msg = await lock(message.from_user, message.text)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, lock_msg)


async def callback_query(call: CallbackQuery, data, bot: CustomBot):
    req = call.data
    call.message.from_user = call.from_user
    match req:
        case 'create_room':
            await bot.send_message(chat_id=call.message.chat.id, text='Введите название комнаты')
            await bot.set_state(call.from_user.id, States.create_room, call.message.chat.id)
        case 'connect_room':
            await bot.send_message(chat_id=call.message.chat.id, text=CALLBACK_TEXTS.connection_room)
            await bot.delete_state(call.from_user.id, call.message.chat.id)
            await bot.set_state(call.from_user.id, States.connect_room, call.message.chat.id)
        case 'change_name':
            await ChangeMyName(bot).run(call.message)
        case 'set_wishes':
            await ChangeWishes(bot).run(call.message)


async def create_room_handler(message: Message, data, bot: CustomBot):
    room_name = message.text
    room_id = await create_room(room_name, message.from_user)
    await bot.reply_to(message, f'Вы создали комнату {room_name} c id {room_id}')
    bot_info = await bot.get_me()
    await bot.send_message(message.chat.id, CALLBACK_TEXTS.link.format(room_name=room_name,
                                                                       bot_name=bot_info.username,
                                                                       room_id=room_id))

    msg = await get_user_info(message.from_user)
    await bot.send_message(message.chat.id, CALLBACK_TEXTS.successfully_created_room.format(room_name=room_name, msg=msg))
    await bot.delete_state(message.from_user.id, message.chat.id)
