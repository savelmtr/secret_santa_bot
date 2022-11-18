import asyncio
import os
import re

from sqlalchemy import update, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from telebot.asyncio_storage import StateMemoryStorage
from telebot.asyncio_handler_backends import State, StatesGroup
from telebot import asyncio_filters
from models import Rooms, Users, Pairs
import random
from cryptography.fernet import Fernet


NUM_PTTRN = re.compile(r'\d+')
TOKEN = os.getenv('TOKEN')
Encoder = Fernet(os.getenv('SECRET').encode())
engine = create_async_engine(
    os.getenv('PG_URI_ASYNC'),
    echo=False
)


class ButtonStorage(StatesGroup):
    connect_room = State()
    create_room = State()
    user_name = State()
    wish_list = State()


AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
bot = AsyncTeleBot(TOKEN)


@bot.message_handler(commands=['help'])
async def send_welcome(message, markup):
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
    """, reply_markup=markup)


async def get_user(user_payload) -> Users:
    req = (
        insert(Users)
        .values(
            id=user_payload.id,
            username=user_payload.username,
            first_name=user_payload.first_name if user_payload.first_name else '',
            last_name=user_payload.last_name if user_payload.last_name else ''
        )
        .on_conflict_do_update(
            index_elements=[Users.id],
            set_=dict(
                first_name=user_payload.first_name if user_payload.first_name else '',
                last_name=user_payload.last_name if user_payload.last_name else ''
            )
        )
        .returning(Users)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        user = q.scalar()
    return user


async def create_room(name: str, user_payload) -> int:
    user = await get_user(user_payload)
    req = insert(Rooms).values(
        name=name,
        creator_id=user.id
    ).returning(Rooms.id)
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        room_id = q.one().id

        up_req = (
            update(Users)
            .where(Users.id == user.id)
            .values(
                room_id=room_id
            )
        )
        await session.execute(up_req)
        return room_id


async def to_room_attach(room_id: int, user_payload) -> tuple[str | None, bool]:
    user = await get_user(user_payload)
    room_id_req = select(Rooms).filter(Rooms.id == room_id)
    attaching = update(Users).where(Users.id == user.id)
    attaching_no_pass = attaching.values(room_id=room_id, candidate_room_id=None)
    attaching_secure = attaching.values(candidate_room_id=room_id, room_id=None)
    async with AsyncSession.begin() as session:
        q = await session.execute(room_id_req)
        room = q.scalar()
        if not room:
            return None, False
        if room.creator_id == user.id:
            # Создателю комнаты вводить пароль незачем.
            await session.execute(attaching_no_pass)
            return room.name, False
        elif room.passkey:
            await session.execute(attaching_secure)
            return room.name, True
        else:
            await session.execute(attaching_no_pass)
            return room.name, False


async def set_user_name_data(name, surname, user_payload) -> str | None:
    user = await get_user(user_payload)
    user_id = user.id
    if user.last_name and user.first_name:
        return ' '.join([user.last_name, user.first_name])
    naming_req = (
        update(Users)
        .where(Users.id == user_id)
        .values(
            first_name=name,
            last_name=surname,
        )
    )
    async with AsyncSession.begin() as session:
        result = await session.execute(naming_req)
        return result


@bot.callback_query_handler(func=lambda call: 'room' in call.data)
async def callback_query(call):
    req = call.data
    if 'create_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text='Введите название комнаты')
        await bot.set_state(call.from_user.id, ButtonStorage.create_room, call.message.chat.id)
    elif 'connect_room' == req:
        await bot.send_message(chat_id=call.message.chat.id, text='Введите номер комнаты')
        await bot.set_state(call.from_user.id, ButtonStorage.connect_room, call.message.chat.id)

@bot.message_handler(state=ButtonStorage.create_room)
async def create_room_(message):
    room_name = message.text
    room_id = await create_room(room_name, message.from_user)
    await bot.reply_to(message, f'Вы создали комнату {room_name} c id {room_id}')


@bot.message_handler(state=ButtonStorage.connect_room)
async def connect_room_(message):
    room_id = message.text
    room_name, is_protected = await to_room_attach(int(room_id), message.from_user)
    if not room_name:
        await bot.reply_to(message, f'Не найдено комнаты c id:{room_id}')
    elif room_name and not is_protected:
        await bot.reply_to(message, f'Вы присоединились к комнате {room_name} c id:{room_id}')
    elif room_name and is_protected:
        await bot.reply_to(
            message, 
            f'Вы присоединились к комнате {room_name} c id:{room_id}.'
            ' Комната заперта, введите пароль с помощью /enlock пароль.'
        )
    # if not room_name:
    #     await bot.reply_to(message, f'Не найдено комнаты c id:{room_id}! Попробуйте еще раз!')
    #     await bot.set_state(message.from_user.id, ButtonStorage.connect_room, message.chat.id)
    # else:
    #     await bot.reply_to(message, f'Вы присоединились к комнате {room_name} c id:{room_id}!')
    #     await bot.send_message(message.chat.id, f'Введите пожалуйста свое имя и фамилию')
    #     await bot.set_state(message.from_user.id, ButtonStorage.user_name, message.chat.id)


@bot.message_handler(state=ButtonStorage.user_name)
async def get_user_name(message):
    name, surname = str(message.text).split(' ')
    result = await set_user_name_data(name, surname, message.from_user)
    await bot.send_message(message.chat.id, f'А теперь введите список желаемых подарков')
    await bot.set_state(message.from_user.id, ButtonStorage.wish_list, message.chat.id)


@bot.message_handler(state=ButtonStorage.wish_list)
async def get_user_name(message):
    payload = message.text
    if not payload:
        await bot.reply_to(message, f'Введите список желаемого.')
        await bot.set_state(message.from_user.id, ButtonStorage.wish_list, message.chat.id)
    else:
        req = (
            update(Users)
            .where(Users.id == message.from_user.id)
            .values(
                wish_string=payload
            )
        )
        async with AsyncSession.begin() as session:
            await session.execute(req)
        await bot.reply_to(message, f'В желаемое добавлено: {payload}')
        await bot.delete_state(message.from_user.id, message.chat.id)


@bot.message_handler(commands=['start'])
async def get_room(message):
    # if not payload:
    create_room_btn = types.InlineKeyboardButton(text='Создать комнату', callback_data='create_room')
    connect_room_btn = types.InlineKeyboardButton(text='Подключиться к комнате', callback_data='connect_room')
    markup = types.InlineKeyboardMarkup()
    markup.add(create_room_btn)
    markup.add(connect_room_btn)
    await send_welcome(message, markup)


# elif 'Присоединиться' in message.text:
#     room_name = await to_room_attach(int(payload), message.from_user)
#     if not room_name:
#         await bot.reply_to(message, f'Не найдено комнаты c id:{payload}')
#     else:
#         await bot.reply_to(message, f'Вы присоединились к комнате {room_name} c id:{payload}')
# else:
#     room_id = await create_room(payload, message.from_user)
#     await bot.reply_to(message, f'Вы создали комнату {payload} c id {room_id}')


@bot.message_handler(commands=['wish'])
async def set_wish(message):
    payload = message.text[6:].strip()
    if not payload:
        await bot.reply_to(message, f'Введите список желаемого.')
    else:
        user = await get_user(message.from_user)
        req = (
            update(Users)
            .where(
                Users.id == user.id
            )
            .values(
                wish_string=payload
            )
        )
        async with AsyncSession.begin() as session:
            await session.execute(req)
        await bot.reply_to(message, f'В желаемое добавлено: {payload}')


@bot.message_handler(commands=['members'])
async def show_members(message):
    user = await get_user(message.from_user)
    if not user.room_id:
        await bot.reply_to(message, f'Вы не подсоединены ни к одной комнате.')
    else:
        room_req = (
            select(Users)
            .join(Rooms, Rooms.id == Users.room_id)
            .filter(
                Rooms.id == user.room_id
            )
        )
        async with AsyncSession.begin() as session:
            q = await session.execute(room_req)
            members = q.scalars().all()
        m_str = '* ' + '\n* '.join([f'@{m.username} {m.first_name} {m.last_name}' for m in members])
        await bot.reply_to(message, m_str)


def combine_pairs(members: list[int]):
    used_ids = set()
    pairs = []
    for m in members:
        taker = m
        while taker == m or taker in used_ids:
            taker = random.choice(members)
        pairs.append((m, taker))
        used_ids.add(taker)
    return pairs


@bot.message_handler(commands=['set_pairs'])
async def set_pairs(message):
    user = await get_user(message.from_user)
    if not user.room_id:
        await bot.reply_to(message, f'Вы не подсоединены ни к одной комнате.')
    else:
        room_req = (
            select(Users.id)
            .join(Rooms, Rooms.id == Users.room_id)
            .filter(
                Rooms.id == user.room_id,
                Rooms.creator_id == user.id
            )
        )
        async with AsyncSession.begin() as session:
            q = await session.execute(room_req)
            members = q.scalars().all()
        if not members:
            await bot.reply_to(message, '''
    Вы не являетесь создателем группы.
    Только создатель может запускать создание пар.
            ''')

        pairs = combine_pairs(members)
        stmt = (
            insert(Pairs)
            .values([
                {
                    'giver_id': giver,
                    'taker_id': taker,
                    'room_id': user.room_id
                }
                for (giver, taker) in pairs
            ])
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Pairs.giver_id, Pairs.room_id],
            set_={
                "taker_id": stmt.excluded.taker_id
            }
        )
        async with AsyncSession.begin() as session:
            await session.execute(stmt)
        await bot.reply_to(message, '''
    Пары созданы.
        ''')


@bot.message_handler(commands=['info'])
async def get_info(message):
    user = await get_user(message.from_user)
    giver = aliased(Users)
    taker = aliased(Users)
    candidate = aliased(Rooms)
    rooms = aliased(Rooms)
    req = (
        select(
            rooms.name.label('room'),
            rooms.id.label('room_id'),
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
            ('Вы собираетесь присоединиться к комнате {}, но пока не ввели пароль.', (data.candidate,)),
            (f'https://t.me/{(await bot.get_me()).username}/?start={{}}', (data.room_id,)),
            ('Ваши пожелания: {}.', (data.my_wishes,)),
            ('Вы дарите подарок: @{} {} {}.', (data.username, data.first_name, data.last_name)),
            ('Пожелания одариваемого: {}.', (data.wish_string, ))
        ):
            if any(args):
                msg += line.format(*map(lambda x: '' if x is None else x, args)) + '\n'
        if msg:
            await bot.reply_to(message, msg)
        else:
            await bot.reply_to(message, "Бот пока с вами не знаком.")


@bot.message_handler(commands=['myrooms'])
async def get_my_rooms(message):
    user = await get_user(message.from_user)
    req = (
        select(Rooms)
        .filter(Rooms.creator_id == user.id)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        rooms = q.scalars().all()
    if not rooms:
        await bot.reply_to(message, 'Вы не являетесь владельцем ни одной комнаты.')
    else:
        msg = '\n'.join([f'{r.id} {r.name}' for r in rooms])
        await bot.reply_to(message, msg)


@bot.message_handler(commands=['reset'])
async def reset_members(message):
    user = await get_user(message.from_user)
    cte = (
        select(Rooms.id)
        .filter(
            Rooms.id == user.room_id,
            Rooms.creator_id == user.id
        )
        .cte('cte')
    )
    req = (
        update(Users)
        .where(
            Users.room_id == select(cte.c.id).scalar_subquery(),
            Users.id != user.id
        )
        .values(
            room_id=None
        )
    )
    async with AsyncSession.begin() as session:
        await session.execute(req)
        q = await session.execute(select(cte.c.id))
        room_name = q.scalar()
    if room_name:
        await bot.reply_to(message, 'Комната очищена от участников, остались одни вы.')
    else:
        await bot.reply_to(message, 'Вы не являетесь создателем этой комнаты либо не состоите пока ни в одной.')


@bot.message_handler(commands=['rename'])
async def rename_room(message):
    payload = message.text[7:].strip()
    if not payload:
        await bot.reply_to(message, 'Вы не ввели нового названия комнаты.')
        return
    user = await get_user(message.from_user)
    req = (
        update(Rooms)
        .where(
            Rooms.id == user.room_id,
            Rooms.creator_id == user.id
        )
        .values(
            name=payload
        )
        .returning(
            Rooms.id,
            Rooms.name
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        res = q.one_or_none()
    if not res:
        await bot.reply_to(message, 'Вы не являетесь создателем комнаты, чтобы менять её название.')
    else:
        await bot.reply_to(message, f'Название комнаты с id:{res.id} изменено на {res.name}')


@bot.message_handler(commands=['lock'])
async def lock(message):
    payload = message.text[6:].strip()
    if not payload:
        passkey = None
    else:
        passkey = Encoder.encrypt(payload.encode()).decode()
    user = await get_user(message.from_user)
    req = (
        update(Rooms)
        .where(
            Rooms.id == user.room_id,
            Rooms.creator_id == user.id
        )
        .values(
            passkey=passkey
        )
        .returning(Rooms.id)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        room_id = q.scalar()
    if room_id is None:
        await bot.reply_to(message, 'Только создатель комнаты может её запереть.')
    elif passkey is None:
        await bot.reply_to(message, 'Пароль комнаты сброшен.')
    else:
        await bot.reply_to(message, 'Пароль комнаты установлен.')


@bot.message_handler(commands=['enlock'])
async def enlock(message):
    payload = message.text[8:].strip()
    if not payload:
        await bot.reply_to(message, 'Вы не ввели пароль.')
        return
    user = await get_user(message.from_user)
    passkey_req = (
        select(Rooms.passkey)
        .filter(
            Rooms.id == user.candidate_room_id
        )
    )
    enlock_req = (
        update(Users)
        .where(Users.id == user.id)
        .values(
            candidate_room_id=None,
            room_id=user.candidate_room_id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(passkey_req)
        passkey = q.scalar()
    if passkey:
        if payload == Encoder.decrypt(passkey.encode()).decode():
            async with AsyncSession.begin() as session:
                await session.execute(enlock_req)
            await bot.reply_to(message, 'Комната открыта.')
        else:
            await bot.reply_to(message, 'Пароль не подходит')
    else:
        await bot.reply_to(message, 'Вводить пароль не требуется.')


if __name__ == '__main__':
    asyncio.run(bot.polling())
