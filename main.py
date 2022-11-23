import asyncio
import os
import re

from cryptography.fernet import Fernet
from sqlalchemy import and_, update
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from telebot import asyncio_filters, types
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot.asyncio_storage import StateMemoryStorage
from telebot.types import Message
from telebot.types import User as TelebotUser

from callback_texts import CALLBACK_TEXTS
from models import Pairs, Rooms, Users
from viewmodel import (AsyncSession, UserCache, create_room, get_max_price, set_max_price,
                       get_members, get_user, get_user_info, is_admin, lock, enlock, reset_members,
                       is_paired, set_pairs, set_user_name_data, set_wishes, rename_room,
                       to_room_attach)


NUM_PTTRN = re.compile(r'\d+')
TOKEN = os.getenv('TOKEN')
Encoder = Fernet(os.getenv('SECRET').encode())


class ButtonStorage(StatesGroup):
    connect_room = State()
    create_room = State()
    user_name = State()
    wish_list = State()
    update_name = State()
    update_wishes = State()
    create_password = State()
    enter_password = State()
    max_price = State()
    rename = State()


bot = AsyncTeleBot(TOKEN, state_storage=StateMemoryStorage())
bot.add_custom_filter(asyncio_filters.StateFilter(bot))


@bot.message_handler(commands=['help'])
async def send_welcome(message: Message, markup):
    await bot.reply_to(message, """\
    Это бот-помощник тайного Деда Мороза.

    /start Название комнаты -- чтобы создать комнату.
    /start номер_комнаты -- присоединиться к уже имеющейся комнате.
    /wish произвольный текст -- записать свои пожелания по подаркам.
    /info -- узнать статус (название комнаты, 
    свои пожелания по подаркам, кому дарим, пожелания одариваемого)
    /myrooms -- информация о комнатах, созданных нами
    /members -- посмотреть список участников комнаты.
    /enlock пароль -- отпереть запертую комнату.


    ** Следующие операции может осуществлять только создатель комнаты **

    * /lock пароль -- установить пароль для присоединения к комнате.
    По умолчанию комната не защищена от присоединения к ней людей.
    Чтобы случайные люди не имели возможности испортить ваш уютный междусобойчик,
    их можно "запирать" паролем. Чтобы сбросить пароль введите /lock.

    * /set_pairs -- сгенерировать дарительные пары.

    * /reset -- удалить всех участников из комнаты.

    * /rename -- переименовать комнату.
    
    * /set_max_price -- установить максимальную цену подарка
    """, reply_markup=markup)


async def button_generator(user_payload: TelebotUser):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton('Участники комнаты 👥'), types.KeyboardButton('Мои данные 📋'))
    markup.row(types.KeyboardButton('Изменить имя ✍'), types.KeyboardButton('Изменить пожелания 🎀'))
    admin = await is_admin(user_payload)
    if admin:
        markup.row(types.KeyboardButton('Сгенерировать пары 🎲'), types.KeyboardButton('Удалить всех участников ❌'))
        markup.row(types.KeyboardButton('Установить пароль 🔒'), types.KeyboardButton('Cбросить пароль 🔓'))
        markup.row(types.KeyboardButton('Установить сумму подарков 💸'), types.KeyboardButton('Переименовать комнату 🪄'))
    return markup


@bot.message_handler(state=ButtonStorage.update_name)
async def update_name(message):
    name_data = str(message.text).split(' ')
    if len(name_data) != 2:
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова 😀')
        await bot.set_state(message.from_user.id, ButtonStorage.user_name, message.chat.id)
    first_name, last_name = name_data
    if not str(first_name).isalpha() or not str(last_name).isalpha():
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова используя только буквы 😀')
        await bot.set_state(message.from_user.id, ButtonStorage.user_name, message.chat.id)
    await set_user_name_data(first_name, last_name, message.from_user)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    markup = await button_generator(message.from_user)
    await bot.reply_to(message, msg, reply_markup=markup)


@bot.message_handler(state=ButtonStorage.update_wishes)
async def update_wishes(message):
    wishes = message.text
    await set_wishes(message.from_user.id, wishes)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user, status='update')
    markup = await button_generator(message.from_user)
    await bot.reply_to(message, msg, reply_markup=markup)


@bot.message_handler(commands=['help'])
async def send_welcome(message, markup):
    await bot.reply_to(message, """\
Хо-хоу-хоу! 🎅

На улице выпал первый снег, а значит, что близится Новый год! 🎆
Добро пожаловать в бот-помощник тайного Деда Мороза.

С помощью этого бота вы можете:
1️⃣ создать комнату или присоединиться к уже созданной;
2️⃣ составить свой список желаний для Вашего тайного Деда Мороза;
3️⃣ сформировать пары участников.
    
Также, в любой момент Вы можете изменить свои данные: пожелания, имя и фамилию.
Чтобы начать собственную игру, нажмите кнопку "Создать комнату", а если хотите присоединиться, то "Подключиться к комнате"
        """, reply_markup=markup)


@bot.message_handler(state=ButtonStorage.create_room)
async def create_room_(message):
    room_name = message.text
    room_id = await create_room(room_name, message.from_user)
    await bot.reply_to(message, f'Вы создали комнату {room_name} c id {room_id}')
    bot_info = await bot.get_me()
    await bot.send_message(message.chat.id, CALLBACK_TEXTS.link.format(room_name=room_name,
                                                                       bot_name=bot_info.username,
                                                                       room_id=room_id))
    markup = await button_generator(message.from_user)

    msg = await get_user_info(message.from_user)
    await bot.send_message(message.chat.id, f'Вы успешно создали комнату {room_name}!\n'
                                            'Ваши данные:\n'
                                            f'{msg}', reply_markup=markup)
    await bot.delete_state(message.from_user.id, message.chat.id)


@bot.callback_query_handler(func=lambda call: 'room' in call.data)
async def callback_query(call):
    req = call.data
    if 'create_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text='Введите название комнаты')
        await bot.set_state(call.from_user.id, ButtonStorage.create_room, call.message.chat.id)
    elif 'connect_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text=CALLBACK_TEXTS.connection_room)
        await bot.delete_state(call.from_user.id, call.message.chat.id)
        await bot.set_state(call.from_user.id, ButtonStorage.connect_room, call.message.chat.id)


@bot.message_handler(state=ButtonStorage.create_password)
async def create_password_(message: Message):
    lock_msg = await lock(message.from_user, message.text)
    markup = await button_generator(message.from_user)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, lock_msg, reply_markup=markup)


@bot.message_handler(state=ButtonStorage.connect_room)
async def connect_room_(message: Message):
    try:
        room_id = int(message.text)
    except ValueError:
        await bot.reply_to(message, f'Не найдено комнаты c id:{message.text}! Попробуйте еще раз!')
        return
    room_name, is_protected = await to_room_attach(room_id, message.from_user)
    if not room_name:
        await bot.reply_to(message, f'Не найдено комнаты c id:{room_id}! Попробуйте еще раз!')
        await bot.set_state(message.from_user.id, ButtonStorage.connect_room, message.chat.id)
    elif room_name and not is_protected:
        await bot.reply_to(message, CALLBACK_TEXTS.connect_to_room.format(room_name=room_name))
        await bot.set_state(message.from_user.id, ButtonStorage.user_name, message.chat.id)

    elif room_name and is_protected:
        await bot.reply_to(
            message,
            f'Хо-хоу-хоу!'
            f'Вы присоединились к комнате {room_name} c id:{room_id}.'
            ' Комната заперта, введите пожалуйста пароль'
        )
        await bot.set_state(message.from_user.id, ButtonStorage.enter_password, message.chat.id)


@bot.message_handler(state=ButtonStorage.enter_password)
async def entering_to_room(message):
    enlocked = await enlock(message.from_user, message.text)
    if enlocked:
        await bot.send_message(message.chat.id, 'Комната открыта 🔓', reply_markup=markup)
        await bot.delete_state(message.from_user.id, message.chat.id)
    else:
        await bot.send_message(message.chat.id, 'Пароль не подходит 😞 Попробуйте еще раз')
        await bot.set_state(message.from_user.id, ButtonStorage.enter_password, message.chat.id)


@bot.message_handler(state=ButtonStorage.user_name)
async def get_user_name(message: Message):
    name_data = str(message.text).split(' ')
    if len(name_data) != 2:
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова 😀')
        await bot.set_state(message.from_user.id, ButtonStorage.user_name, message.chat.id)
    first_name, last_name = name_data
    if not str(first_name).isalpha() or not str(last_name).isalpha():
        await bot.reply_to(message, 'Введите пожалуйста Имя и Фамилию в 2 слова используя только буквы 😀')
        await bot.set_state(message.from_user.id, ButtonStorage.user_name, message.chat.id)
    await set_user_name_data(first_name, last_name, message.from_user)
    price = await get_max_price(message.from_user.id)
    await bot.send_message(message.chat.id, CALLBACK_TEXTS.wish_message.format(max_price=price))
    await bot.set_state(message.from_user.id, ButtonStorage.wish_list, message.chat.id)


@bot.message_handler(state=ButtonStorage.wish_list)
async def get_user_wishes(message: Message):
    payload = message.text
    if not payload:
        await bot.set_state(message.from_user.id, ButtonStorage.wish_list, message.chat.id)
    else:
        await set_wishes(message.from_user.id, payload)
    await bot.delete_state(message.from_user.id, message.chat.id)
    msg = await get_user_info(message.from_user)
    markup = await button_generator(message.from_user)
    await bot.reply_to(message, msg, reply_markup=markup)


@bot.message_handler(state=ButtonStorage.max_price)
async def enter_max_price(message):
    price_message = await set_max_price(message.from_user, message.text)
    markup = await button_generator(message.from_user)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, price_message, reply_markup=markup)


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
                await bot.set_state(user.id, ButtonStorage.enter_password, message.chat.id)
            else:
                await bot.reply_to(message, CALLBACK_TEXTS.connect_to_room.format(room_name=room_name))
                await bot.set_state(user.id, ButtonStorage.user_name, message.chat.id)
        else:
            markup = await button_generator(message.from_user)
            await bot.send_message(message.chat.id, 'Хо-хо-хо! Вы вернулись!', reply_markup=markup)


@bot.message_handler(content_types=['text'])
async def button_text_handler(message):
    command = message.text
    admin = await is_admin(message.from_user)
    markup = await button_generator(message.from_user)
    msg = ''
    match command:
        case 'Участники комнаты 👥':
            msg = await get_members(message.from_user)
            await bot.reply_to(message, msg, reply_markup=markup)
        case 'Мои данные 📋':
            paired = await is_paired(message.from_user)
            if paired:
                await get_info(message)
            else:
                msg = await get_user_info(message.from_user, status='info')
                await bot.reply_to(message, msg, reply_markup=markup)
        case 'Изменить имя ✍':
            await bot.send_message(message.chat.id, 'Введите Ваши имя и фамилию и Санта исправит их 🎅 ✍')
            await bot.set_state(message.from_user.id, ButtonStorage.update_name, message.chat.id)
        case 'Изменить пожелания 🎀':
            await bot.send_message(message.chat.id, 'Введите Ваши пожелания и Санта исправит их 🎅 🎀')
            await bot.set_state(message.from_user.id, ButtonStorage.update_wishes, message.chat.id)
        case 'Сгенерировать пары 🎲':
            if admin:
                pairs_set = await set_pairs(message.from_user)
                if pairs_set:
                    await bot.send_message(message.chat.id, 'Пары сгенерированы 🎀')
                else:
                    await bot.send_message(message.chat.id, 'Вы один-одинёшенек в комнате 😧')
            else:
                await bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
        case 'Удалить всех участников ❌':
            if admin:
                reset_txt = await reset_members(message.from_user)
                await bot.send_message(message.chat.id, reset_txt)
            else:
                await bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
        case 'Установить пароль 🔒':
            if admin:
                await bot.send_message(message.chat.id, 'Введите пожалуйста пароль')
                await bot.set_state(message.from_user.id, ButtonStorage.create_password, message.chat.id)
            else:
                await bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
        case 'Cбросить пароль 🔓':
            if admin:
                lock_msg = await lock(message.from_user)
                await bot.send_message(message.chat.id, lock_msg, reply_markup=markup)
            else:
                await bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
        case 'Установить сумму подарков 💸':
            if admin:
                await bot.send_message(message.chat.id, 'Введите максимальную цену подарка')
                await bot.set_state(message.from_user.id, ButtonStorage.max_price, message.chat.id)
            else:
                await bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
        case 'Переименовать комнату 🪄':
            if admin:
                await bot.send_message(message.chat.id, 'Введите новое название комнаты')
                await bot.set_state(message.from_user.id, ButtonStorage.rename, message.chat.id)
            else:
                await bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
        case _:
            pass


@bot.message_handler(state=ButtonStorage.rename)
async def try_rename_room(message):
    rename_msg = await rename_room(message.from_user, message.text)
    markup = await button_generator(message.from_user)
    await bot.delete_state(message.from_user.id, message.chat.id)
    await bot.send_message(message.chat.id, rename_msg, reply_markup=markup)


@bot.message_handler(commands=['info'])
async def get_info(message: Message):
    user = await get_user(message.from_user)
    giver = aliased(Users)
    taker = aliased(Users)
    candidate = aliased(Rooms)
    rooms = aliased(Rooms)
    req = (
        select(
            rooms.name.label('room'),
            rooms.id.label('room_id'),
            rooms.max_price,
            candidate.name.label('candidate'),
            candidate.id.label('candidate_id'),
            giver.wish_string.label('my_wishes'),
            taker.first_name,
            taker.last_name,
            taker.username,
            taker.wish_string
        )
        .join(rooms, rooms.id == giver.room_id, isouter=True)
        .join(candidate, candidate.id == giver.candidate_room_id, isouter=True)
        .join(Pairs, and_(Pairs.giver_id == giver.id, Pairs.room_id == rooms.id), isouter=True)
        .join(taker, taker.id == Pairs.taker_id, isouter=True)
        .filter(
            giver.id == user.id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        data = q.one_or_none()
        msg = ''
        for line, args in (
                ('Вы подсоединены к комнате {}.', (data.room,)),
                ('Максимальная цена подарка: {}', (data.max_price,)),
                ('Вы собираетесь присоединиться к комнате {}, но пока не ввели пароль.', (data.candidate,)),
                (f'Ссылка на бота: https://t.me/{(await bot.get_me()).username}/?start={{}}', (data.room_id,)),
                ('Ваши пожелания: {}.', (data.my_wishes,)),
                ('Вы дарите подарок: @{} {} {}.', (data.username, data.first_name, data.last_name)),
                ('Пожелания одариваемого: {}.', (data.wish_string,))
        ):
            if any(args):
                msg += line.format(*map(lambda x: '' if x is None else x, args)) + '\n'
        markup = await button_generator(message.from_user)
        if msg:
            await bot.reply_to(message, msg, reply_markup=markup)
        else:
            await bot.reply_to(message, "Бот пока с вами не знаком.", reply_markup=markup)


if __name__ == '__main__':
    asyncio.run(bot.polling())
