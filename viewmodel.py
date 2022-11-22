import os
import random

from asyncache import cached
from cachetools import TTLCache
from sqlalchemy import and_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from telebot.types import User as TelebotUser

from callback_texts import CALLBACK_TEXTS
from models import Pairs, Rooms, Users


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


async def get_user_info(user_payload: TelebotUser, status='connect'):
    user = await get_user(user_payload)
    giver = aliased(Users)
    req = (
        select(
            Rooms.name.label('room'),
            Rooms.id.label('room_id'),
            giver.first_name,
            giver.last_name,
            giver.username,
            giver.wish_string.label('my_wishes'),
        )
        .join(Rooms, Rooms.id == giver.room_id, isouter=True)
        .filter(
            giver.id == user.id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        data = q.one_or_none()
        if status == 'connect':
            msg = CALLBACK_TEXTS.congratulations.format(
                room=data.room,
                my_wishes=data.my_wishes,
                username=data.username,
                first_name=data.first_name,
                last_name=data.last_name
            )
        elif status == 'update':
            msg = CALLBACK_TEXTS.update.format(
                my_wishes=data.my_wishes,
                    username=data.username,
                    first_name=data.first_name,
                    last_name=data.last_name
                )
        else:
            msg = CALLBACK_TEXTS.info.format(
                room=data.room,
                my_wishes=data.my_wishes,
                username=data.username,
                first_name=data.first_name,
                last_name=data.last_name
            )
        return msg


async def is_admin(user_payload: TelebotUser):
    user = await get_user(user_payload)
    req = (
        select(Rooms.id)
        .filter(
            Rooms.creator_id == user.id,
            Rooms.id == user.room_id
        )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        result = q.scalar()
        return True if result else False


async def get_max_price(user_id: int):
    req = (
        select(Rooms.max_price)
        .join(Users, Rooms.id == Users.room_id)
        .filter(Users.id == user_id)
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        price = q.scalar()
        if not price:
            return 'любая'
        return price


async def is_paired(user_payload: TelebotUser):
    user = await get_user(user_payload)
    req = (
        select(Pairs.giver_id)
        .filter(
            Pairs.giver_id == user.id,
            Pairs.room_id == user.room_id
    )
    )
    async with AsyncSession.begin() as session:
        q = await session.execute(req)
        res = q.scalar()
    return True if res else False


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
