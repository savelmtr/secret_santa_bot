import re
from telebot.async_telebot import AsyncTeleBot
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Rooms, Users
from sqlalchemy import update, insert, delete
from sqlalchemy.future import select
from copy import copy
from random import randint


NUM_PTTRN = re.compile(r'\d+')
TOKEN = os.getenv('TOKEN')
engine = create_async_engine(
    os.getenv('PG_URI'),
    echo=False,
)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)
bot = AsyncTeleBot(TOKEN)


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


    ** Следующие операции может осуществлять только создатель комнаты **

    * /lock пароль -- установить пароль для присоединения к комнате.
    По умолчанию комната не защищена от присоединения к ней людей.
    Чтобы случайные люди не имели возможности испортить ваш уютный междусобойчик,
    их можно "запирать" паролем. Чтобы сбросить пароль введите /lock.

    * /members -- посмотреть список участников комнаты. 

    * /set_pairs -- сгенерировать дарительные пары.

    * /reset -- удалить всех участников из комнаты.

    * /rename -- переименовать комнату.
    """)


async def get_user(user_payload) -> Users:
    req = select(Users).filter(Users.id == user_payload.id)
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        user = q.one()
        if not user:
            user = Users(
                id=user_payload.id,
                username=user_payload.username,
                first_name=user_payload.first_name,
                last_name=user_payload.last_name
            )
            session.add(user)
            await session.commit()
    return user


async def create_room(name: str, user_payload) -> int:
    user = await get_user(user_payload)
    req = insert(Rooms).values(
        name=payload,
        creator_id=user.id
    ).returning(Rooms.id)
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        return q.one().id


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
        room = q.one()
        if not room:
            return
        await session.execute(attaching_req)
        return room.name


@bot.message_handler(commands=['start'])
async def get_room(message):
    payload = message.text[6:].strip()
    if not payload:
        await send_welcome(message)
    elif NUM_PTTRN.match(payload):
        room_name = await to_room_attach(int(payload), message.from_user)
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
    Только создатель может просматривать состав группы.
            ''')
        else:
            m_str = '\n* '.join([f'@{m.userid} {m.first_name} {m.last_name}' for m in members])
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
        else:
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


asyncio.run(bot.polling())
