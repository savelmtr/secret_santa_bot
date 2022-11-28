import asyncio
import os
import re

from cryptography.fernet import Fernet
from sqlalchemy import and_, update
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from telebot import asyncio_filters, types
from telebot.async_telebot import AsyncTeleBot, REPLY_MARKUP_TYPES
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


class CustomBot(AsyncTeleBot):

    def __init__(self, *args, **kwargs):
        async def process_button_press(message: Message):
            btnset = self.get_available_buttonset()
            if not btnset:
                return
            for btn in (b for row in btnset.buttons for b in row):
                if message.text == btn.name:
                    await btn.run(message)
                    return

        super().__init__(*args, **kwargs)
        self.button_sets = []
        self.message_handler(content_types=['text'])(process_button_press)


    def add_button_set(self, button_set: AbstractButtonSet):
        self.button_sets.append(button_set(self))


    def get_available_buttonset(self):
        available_bs = [
            bs for bs in self.button_sets if bs.is_available(message)
        ]
        return available_bs[0] if available_bs else None


    async def markup_message(
        self,
        message: Message,
        text:str,
        reply_markup: None| REPLY_MARKUP_TYPES = None
    ):
        reply_markup = kwargs.get('reply_markup', self.get_available_buttonset())
        self.send_message(message.chat.id, text, reply_markup=reply_markup)


tbot = CustomBot(TOKEN, state_storage=StateMemoryStorage())
tbot.add_button_set(AdminButtonSet)
tbot.add_button_set(UserButtonSet)
