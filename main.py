import re
from telebot.async_telebot import AsyncTeleBot
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from models import Rooms, Users
from sqlalchemy import update, insert, func, cast, case
from sqlalchemy.future import select


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
    user = get_user(message.from_user)
        req = insert(Rooms).values(
            name=payload,
            creator_id=user.id
        ).returning(Rooms.id)
        async with AsyncSession.begin() as session:
            q = await session.execute(req)
            return q.one().id


async def to_room_attach(room_id: int) -> str|None:
    room_id_req = select(Rooms.id).filter(Rooms.id == room_id)
    async with AsyncSession.begin() as session:
        q = await session.execute(room_id_req)
        room_id = q.one().id
        # TODO: Закончить функцию


@bot.message_handler(commands=['start'])
async def get_room(message):
    #    print(message.from_user.id, message.from_user.username)
    payload = message.text[6:].strip()
    if not payload:
        await bot.reply_to(message, 'Вы не ввели ни номера комнаты, ни названия новой комнаты. Для справки /help.')
    elif NUM_PTTRN.match(payload):
        await bot.reply_to(message, f'Вы присоединились к комнате {payload}')
    else:
        room_id = await create_room(payload, message.from_user)
        await bot.reply_to(message, f'Вы создали комнату {payload} c id {room_id}')


asyncio.run(bot.polling())
