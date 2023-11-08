import os
import random

from asyncache import cached
from cachetools import TTLCache
from sqlalchemy import update, func, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from telebot.types import User as TelebotUser

from lib.callback_texts import CALLBACK_TEXTS
from models import Pairs, Rooms, Users
from cryptography.fernet import Fernet
from typing import Literal


Encoder = Fernet(os.getenv('SECRET').encode())
UserCache = TTLCache(1024, 60)
engine = create_async_engine(
    os.getenv('PG_URI_ASYNC'),
    echo=False
)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)


@cached(UserCache, lambda x: x.id)
async def get_user(user_payload: TelebotUser) -> Users:
    stmt = (
        insert(Users)
        .values(
            id=user_payload.id,
            username=user_payload.username if user_payload.username else '',
            first_name=user_payload.first_name if user_payload.first_name else '',
            last_name=user_payload.last_name if user_payload.last_name else ''
        )
    )
    stmt = (
        stmt.on_conflict_do_update(
            index_elements=[Users.id],
            set_=dict(
                username=stmt.excluded.username
            )
        )
        .returning(Users)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(stmt)
        user = q.scalar()
    return user


async def create_room(name: str, user_payload: TelebotUser) -> int:
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
    UserCache.clear()
    return room_id


async def to_room_attach(room_id: int, user_payload: TelebotUser) -> tuple[str | None, bool]:
    user = await get_user(user_payload)
    room_id_req = select(Rooms).filter(Rooms.id == room_id)
    attaching = update(Users).where(Users.id == user.id)
    attaching_no_pass = attaching.values(room_id=room_id, candidate_room_id=None)
    attaching_secure = attaching.values(candidate_room_id=room_id, room_id=None)
    UserCache.clear()
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


async def set_user_name_data(name, surname, user_payload: TelebotUser) -> None:
    user = await get_user(user_payload)
    user_id = user.id
    naming_req = (
        update(Users)
        .where(Users.id == user_id)
        .values(
            first_name=name,
            last_name=surname,
        )
    )
    async with AsyncSession.begin() as session:
        await session.execute(naming_req)
    UserCache.clear()


async def get_user_info(user_payload: TelebotUser, status: Literal['connect', 'update', 'info']='connect'):
    user = await get_user(user_payload)
    giver = aliased(Users)
    taker = aliased(Users)
    req = (
        select(
            Rooms.name.label('room'),
            Rooms.id.label('room_id'),
            Rooms.max_price,
            giver.first_name,
            giver.last_name,
            giver.username,
            giver.wish_string.label('my_wishes'),
            taker.first_name.label('taker_first_name'),
            taker.last_name.label('taker_last_name'),
            taker.username.label('taker_username'),
            taker.wish_string
        )
        .join(Rooms, Rooms.id == giver.room_id)
        .join(Pairs, and_(Pairs.giver_id == giver.id, Pairs.room_id == Rooms.id), isouter=True)
        .join(taker, taker.id == Pairs.taker_id, isouter=True)
        .filter(
            giver.id == user.id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        data = q.one_or_none()
        if data is None:
            return 'Ошибка базы данных при попытке получить информацию о пользователе.'
    match status:
        case 'connect':
            msg = CALLBACK_TEXTS.info_congrats.format(room=data.room)
        case 'update':
            msg = CALLBACK_TEXTS.info_update
            msg += CALLBACK_TEXTS.info_in_room.format(room=data.room)
        case 'info':
            msg = CALLBACK_TEXTS.info_in_room.format(room=data.room)
        case _:
            return ''
    
    for kwargs, callback_text in (
        ({'my_wishes': data.my_wishes}, CALLBACK_TEXTS.info_wishes),
        (
            {'username': data.username, 'first_name': data.first_name, 'last_name':data.last_name},
            CALLBACK_TEXTS.info_name
        ),
        (
            {
                'taker_username': data.taker_username,
                'taker_first_name': data.taker_first_name,
                'taker_last_name':data.taker_last_name
            },
            CALLBACK_TEXTS.info_taker
        ),
        ({'taker_wishes': data.wish_string}, CALLBACK_TEXTS.info_taker_wishes),
        ({'max_price': data.max_price}, CALLBACK_TEXTS.info_max_price),
    ):
        if any(kwargs.values()):
            msg += callback_text.format(**kwargs)
    return msg


async def is_attached(chat_id: int, is_admin: bool=False) -> bool:
    cond = Users.id == Rooms.creator_id if is_admin else Users.id != Rooms.creator_id
    req = (
        select(Rooms.id)
        .join(Users, and_(Users.room_id == Rooms.id, cond))
        .filter(
            Users.id == chat_id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        result = q.scalar()
        return True if result else False


async def set_wishes(user_id: int, wishes: str):
    req = (
        update(Users)
        .where(Users.id == user_id)
        .values(
            wish_string=wishes
        )
    )
    async with AsyncSession.begin() as session:
        await session.execute(req)
    UserCache.clear()


async def get_members(user_payload: TelebotUser):
    user = await get_user(user_payload)
    if not user.room_id:
        m_str = 'Вы не подсоединены ни к одной комнате.'
    else:
        room_req = (
            select(
                func.row_number().over().label('rnum'),
                Users.username,
                Users.first_name,
                Users.last_name
            )
            .join(Rooms, Rooms.id == Users.room_id)
            .filter(
                Rooms.id == user.room_id
            )
        )
        async with AsyncSession.begin() as session:
            q = await session.execute(room_req)
            members = q.all()
        m_str = '\n'.join([f'{m.rnum}. @{m.username} {m.first_name} {m.last_name}' for m in members])
    return m_str


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


async def set_pairs(user_payload: TelebotUser) -> bool:
    user = await get_user(user_payload)
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
    if len(members) < 2:
        return False

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
    return True


async def lock(user_payload: TelebotUser, text: str|None=None) -> str:
    if not text:
        passkey = None
    else:
        passkey = Encoder.encrypt(text.encode()).decode()
    user = await get_user(user_payload)
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
        return 'Только создатель комнаты может её запереть.'
    elif passkey is None:
        return 'Пароль комнаты сброшен.'
    else:
        return f'Пароль комнаты установлен. Пароль: {text}'

    
async def set_max_price(user_payload: TelebotUser, text: str='') -> str:
    user = await get_user(user_payload)
    req = (
        update(Rooms)
        .where(
            Rooms.id == user.room_id,
            Rooms.creator_id == user.id
        )
        .values(max_price=text)
        .returning(Rooms.name)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        name = q.scalar()
    if not name:
        return f'Только создатель комнаты может устанавливать минимальную цену подарка в ней.'
    elif text:
        return f'Установлена минимальная цена подарка для комнаты {name} ({text} 💸).'
    else:
        return f'Сброшена минимальная цена подарка для комнаты {name}.'

    
async def enlock(user_payload: TelebotUser, text: str='') -> bool:
    user = await get_user(user_payload)
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

    if text == Encoder.decrypt(passkey.encode()).decode():
        async with AsyncSession.begin() as session:
            await session.execute(enlock_req)
        UserCache.clear()
        return True
    else:
        return False

    
async def rename_room(user_payload: TelebotUser, text: str='') -> str:
    if not text:
        return 'Вы не ввели нового названия комнаты.'
    user = await get_user(user_payload)
    req = (
        update(Rooms)
        .where(
            Rooms.id == user.room_id,
            Rooms.creator_id == user.id
        )
        .values(name=text)
        .returning(
            Rooms.id,
            Rooms.name
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        res = q.one_or_none()
    if not res:
        return 'Вы не являетесь создателем комнаты, чтобы менять её название.'
    else:
        return f'Название комнаты с id:{res.id} изменено на {res.name}'

    
async def reset_members(user_payload: TelebotUser) -> str:
    user = await get_user(user_payload)
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
        .values(room_id=None)
    )
    UserCache.clear()
    async with AsyncSession.begin() as session:
        await session.execute(req)
        q = await session.execute(select(cte.c.id))
        room_name = q.scalar()
    if room_name:
        return 'Комната очищена от участников, остались одни вы.'
    else:
        return 'Вы не являетесь создателем этой комнаты либо не состоите пока ни в одной.'


async def get_my_rooms(user_payload: TelebotUser) -> str:
    user = await get_user(user_payload)
    req = (
        select(Rooms)
        .filter(Rooms.creator_id == user.id)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        rooms = q.scalars().all()
    if not rooms:
        return 'Вы не являетесь владельцем ни одной комнаты.'
    else:
        msg = '\n'.join([f'{r.id} {r.name}' for r in rooms])
        return msg
    

async def get_pairs(user_payload: TelebotUser):
    giver = aliased(Users)
    taker = aliased(Users)
    req = (
        select(
            taker.id,
            giver.username,
            giver.first_name,
            giver.last_name,
            giver.wish_string
        )
        .select_from(Users)
        .join(Pairs, Users.room_id == Pairs.room_id)
        .join(giver, giver.id == Pairs.giver_id)
        .join(taker, taker.id == Pairs.taker_id)
        .filter(Users.id == user_payload.id)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        data = q.all()
    return data
