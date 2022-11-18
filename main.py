import asyncio
import os
import re

from sqlalchemy import update, insert, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from telebot.async_telebot import AsyncTeleBot

from models import Rooms, Users, Pairs
import random


NUM_PTTRN = re.compile(r'\d+')
TOKEN = os.getenv('TOKEN')
engine = create_async_engine(
    os.getenv('PG_URI_ASYNC'),
    echo=False,
)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
bot = AsyncTeleBot(TOKEN)

# TODO: lock

@bot.message_handler(commands=['help'])
async def send_welcome(message):
    await bot.reply_to(message, """\
    Это бот-помощник тайного Деда Мороза.

    /start Название комнаты -- чтобы создать комнату.
    /start номер_комнаты -- присоединиться к уже имеющейся комнате.
    /wish произвольный текст -- записать свои пожелания по подаркам.
    /info -- узнать статус (название комнаты, 
    свои пожелания по подаркам, кому дарим, пожелания одариваемого)
    /myrooms -- информация о комнатах, созданных нами
    /members -- посмотреть список участников комнаты. 


    ** Следующие операции может осуществлять только создатель комнаты **

    * /lock пароль -- установить пароль для присоединения к комнате.
    По умолчанию комната не защищена от присоединения к ней людей.
    Чтобы случайные люди не имели возможности испортить ваш уютный междусобойчик,
    их можно "запирать" паролем. Чтобы сбросить пароль введите /lock.

    * /set_pairs -- сгенерировать дарительные пары.

    * /reset -- удалить всех участников из комнаты.

    * /rename -- переименовать комнату.
    """)


async def get_user(user_payload) -> Users:
    req = select(Users).filter(Users.id == user_payload.id)
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        user = q.scalar()
        if not user:
            user = Users(
                id=user_payload.id,
                username=user_payload.username,
                first_name=user_payload.first_name if user_payload.first_name else '',
                last_name=user_payload.last_name if user_payload.last_name else ''
            )
            session.add(user)
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


async def to_room_attach(room_id: int, user_payload) -> str|None:
    user = await get_user(user_payload)
    user_id = user.id
    room_id_req = select(Rooms.name).filter(Rooms.id == room_id)
    attaching_req = (
        update(Users)
        .where(Users.id == user_id)
        .values(
            room_id=room_id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(room_id_req)
        room = q.scalar()
        if not room:
            return
        await session.execute(attaching_req)
        return room


@bot.message_handler(commands=['start'])
async def get_room(message):
    payload = message.text[6:].strip()
    if not payload:
        await send_welcome(message)
    elif NUM_PTTRN.match(payload):
        room_name = await to_room_attach(int(payload), message.from_user)
        if not room_name:
            await bot.reply_to(message, f'Не найдено комнаты c id:{payload}')
        else:
            await bot.reply_to(message, f'Вы присоединились к комнате {room_name} c id:{payload}')
    else:
        room_id = await create_room(payload, message.from_user)
        await bot.reply_to(message, f'Вы создали комнату {payload} c id {room_id}')


@bot.message_handler(commands=['wish'])
async def set_wish(message):
    payload = message.text[6:].strip()
    if not payload:
        await bot.reply_to(message, f'Введите список желаемого.')
    else:
        req = (
            update(Users)
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
        m_str = '\n* '.join([f'@{m.username} {m.first_name} {m.last_name}' for m in members])
        await bot.reply_to(message, m_str)


async def combine_pairs(members: list[int]):
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

        pairs = await combine_pairs([m.id for m in members])
        async with AsyncSession.begin() as session:
            del_req = (
                delete(Pairs)
                .where(Pairs.giver_id.in_([p[0] for p in pairs]))
            )
            await session.execute(del_req)
            await session.commit()
            for (giver, taker) in pairs:
                session.add(
                    Pairs(
                        giver_id=giver,
                        taker_id=taker
                    )
                )
        await bot.reply_to(message, '''
    Пары созданы.
        ''')


@bot.message_handler(commands=['info'])
async def get_info(message):
    user = await get_user(message.from_user)
    giver = aliased(Users)
    taker = aliased(Users)
    req = (
        select(
            Rooms.name.label('room'),
            Rooms.id.label('room_id'),
            giver.wish_string.label('my_wishes'),
            taker.first_name,
            taker.last_name,
            taker.username,
            taker.wish_string
        )
        .join(Pairs, Pairs.giver_id == giver.id, isouter=True)
        .join(taker, taker.id == Pairs.taker_id, isouter=True)
        .join(Rooms, Rooms.id == giver.room_id, isouter=True)
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


asyncio.run(bot.polling())
