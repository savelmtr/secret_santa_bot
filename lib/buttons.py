from telebot.types import Message
from lib.viewmodel import (is_attached, get_pairs,
                       get_members, get_user_info, lock, reset_members,
                       set_pairs)
from typing import Callable
from lib.states import States
from lib.base import AbstractButton, AbstractButtonSet


def check_if_admin(method: Callable):
    async def wrapped(self, message: Message):
        admin = await is_attached(message.chat.id, True)
        if admin:
            return await method(self, message)
        else:
            await self.bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')
    return wrapped


class GetTeamMates(AbstractButton):
    name = 'Участники комнаты 👥'

    async def run(self, message: Message):
        msg = await get_members(message.from_user)
        await self.bot.send_message(message.chat.id, msg)


class GetMyData(AbstractButton):
    name = 'Мои данные 📋'

    async def run(self, message: Message):
        msg = await get_user_info(message.from_user, status='info')
        await self.bot.send_message(message.chat.id, msg)


class ChangeMyName(AbstractButton):
    name = 'Изменить имя ✍'

    async def run(self, message: Message):
        await self.bot.send_message(
            message.chat.id,
            'Напишите как вас зовут, чтобы ваши друзья знали, кому они дарят подарок 🎅 ✍'
        )
        await self.bot.set_state(message.from_user.id, States.update_name, message.chat.id)


class ChangeWishes(AbstractButton):
    name = 'Изменить пожелания 🎀'

    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите ваши пожелания 🎅 🎀')
        await self.bot.set_state(message.from_user.id, States.update_wishes, message.chat.id)


class GeneratePairs(AbstractButton):
    name = 'Сгенерировать пары 🎲'

    @check_if_admin
    async def run(self, message: Message):
        pairs_set = await set_pairs(message.from_user)
        if pairs_set:
            await self.bot.send_message(message.chat.id, 'Пары сгенерированы 🎀')
            for mem_id, username, first_n, last_n, wishes in await get_pairs(message.from_user):
                await self.bot.send_message(mem_id, f'Ваша пара: @{username} {first_n} {last_n}. Пожелания: {wishes}')
        else:
            await self.bot.send_message(message.chat.id, 'Вы один-одинёшенек в комнате 😧')


class DeleteMembers(AbstractButton):
    name = 'Удалить всех участников ❌'

    @check_if_admin
    async def run(self, message: Message):
        reset_txt = await reset_members(message.from_user)
        await self.bot.send_message(message.chat.id, reset_txt)


class SetPassword(AbstractButton):
    name = 'Установить пароль 🔒'

    @check_if_admin
    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите пожалуйста пароль')
        await self.bot.set_state(message.from_user.id, States.create_password, message.chat.id)


class DeletePassword(AbstractButton):
    name = 'Cбросить пароль 🔓'

    @check_if_admin
    async def run(self, message: Message):
        lock_msg = await lock(message.from_user)
        await self.bot.send_message(message.chat.id, lock_msg)


class SetMaxPrice(AbstractButton):
    name = 'Установить сумму подарков 💸'

    @check_if_admin
    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите минимальную цену подарка')
        await self.bot.set_state(message.from_user.id, States.max_price, message.chat.id)


class RenameRoom(AbstractButton):
    name = 'Переименовать комнату 🪄'

    @check_if_admin
    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите новое название комнаты')
        await self.bot.set_state(message.from_user.id, States.rename, message.chat.id)


class UserButtonSet(AbstractButtonSet):
    buttons = (
        (GetTeamMates, GetMyData),
        (ChangeMyName, ChangeWishes)
    )

    async def is_available(self, chat_id: int | str):
        return await is_attached(chat_id)


class AdminButtonSet(AbstractButtonSet):
    buttons = (
        (GetTeamMates, GetMyData),
        (ChangeMyName, ChangeWishes),
        (GeneratePairs, DeleteMembers),
        (SetPassword, DeletePassword),
        (SetMaxPrice, RenameRoom)
    )

    async def is_available(self, chat_id: int | str):
        return await is_attached(chat_id, True)
