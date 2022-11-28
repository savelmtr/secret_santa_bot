from abc import ABC, abstractmethod
from telebot.types import Message, KeyboardButton, ReplyKeyboardMarkup
from telebot.async_telebot import AsyncTeleBot
from viewmodel import (create_room, get_max_price, set_max_price,
                       get_members, get_user, get_user_info, is_admin, lock, enlock, reset_members,
                       is_paired, set_pairs, set_user_name_data, set_wishes, rename_room,
                       to_room_attach)


class AbstractButton(ABC, KeyboardButton):
    name: str

    def __init__(self, bot: AsyncTeleBot):
        super(KeyboardButton).__init__(self.name)
        self.bot = bot

    @abstractmethod
    async def run(self, message: Message):
        pass


def check_if_admin(method: Callable):
    async def wrapped(self, message: Message):
        admin = await is_admin(message.from_user)
        if admin:
            await method(self, message)
        else:
            await self.bot.send_message(message.chat.id, 'Упс! Вы не являетесь администратором комнаты, не шалите 😘')


class GetTeamMates(AbstractButton):
    name = 'Участники комнаты 👥'

    async def run(self, message: Message):
        msg = await get_members(message.from_user)
        await self.bot.send_message(message.chat.id, msg)


class GetMyData(AbstractButton):
    name = 'Мои данные 📋'

    async def run(self, message: Message):
        paired = await is_paired(message.from_user)
        if paired:
            await get_info(message)
        else:
            msg = await get_user_info(message.from_user, status='info')
            await self.bot.send_message(message.chat.id, msg)


class ChangeMyName(AbstractButton):
    name = 'Изменить имя ✍'

    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите Ваши имя и фамилию и Санта исправит их 🎅 ✍')
        await self.bot.set_state(message.from_user.id, ButtonStorage.update_name, message.chat.id)


class ChangeWishes(AbstractButton):
    name = 'Изменить пожелания 🎀'

    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите Ваши пожелания и Санта исправит их 🎅 🎀')
        await self.bot.set_state(message.from_user.id, ButtonStorage.update_wishes, message.chat.id)


class GeneratePairs(AbstractButton):
    name = 'Сгенерировать пары 🎲'

    @check_if_admin
    async def run(self, message: Message):
        pairs_set = await set_pairs(message.from_user)
        if pairs_set:
            await self.bot.send_message(message.chat.id, 'Пары сгенерированы 🎀')
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
        await self.bot.set_state(message.from_user.id, ButtonStorage.create_password, message.chat.id)


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
        await self.bot.send_message(message.chat.id, 'Введите максимальную цену подарка')
        await self.bot.set_state(message.from_user.id, ButtonStorage.max_price, message.chat.id)


class RenameRoom(AbstractButton):
    name = 'Переименовать комнату 🪄'

    @check_if_admin
    async def run(self, message: Message):
        await self.bot.send_message(message.chat.id, 'Введите новое название комнаты')
        await self.bot.set_state(message.from_user.id, ButtonStorage.rename, message.chat.id)


class AbstractButtonSet(ABC, ReplyKeyboardMarkup):
    resize_keyboard: bool = True
    buttons: tuple[tuple[AbstractButton]]

    def __init__(self, bot: AsyncTeleBot):
        super(ReplyKeyboardMarkup).__init__(resize_keyboard=self.resize_keyboard)
        for row in self.buttons:
            self.row(*[b(bot) for b in row])

    @abstractmethod
    async def is_available(self, message: Message):
        pass


class UserButtonSet(AbstractButtonSet):
    buttons = (
        (GetTeamMates, GetMyData),
        (ChangeMyName, ChangeWishes)
    )

    async def is_available(self, message: Message):
        return not await is_admin(message.from_user)


class AdminButtonSet(AbstractButtonSet):
    buttons = (
        (GetTeamMates, GetMyData),
        (ChangeMyName, ChangeWishes),
        (GeneratePairs, DeleteMembers),
        (SetPassword, DeletePassword),
        (SetMaxPrice, RenameRoom)
    )

    async def is_available(self, message: Message):
        return await is_admin(message.from_user)
