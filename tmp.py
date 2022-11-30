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


    def get_available_buttonset(self, chat_id: int | str):
        available_bs = [
            bs for bs in self.button_sets if bs.is_available(chat_id)
        ]
        return available_bs[0] if available_bs else None

    async def send_message(
            self, chat_id: int | str, text: str, 
            parse_mode:  None | str=None, 
            entities:  None|list[types.MessageEntity]=None,
            disable_web_page_preview:  None|bool=None, 
            disable_notification:  None|bool=None, 
            protect_content:  None|bool=None,
            reply_to_message_id:  None|int=None, 
            allow_sending_without_reply:  None|bool=None,
            reply_markup:  None|REPLY_MARKUP_TYPES=None,
            timeout:  None|int=None,
            message_thread_id:  None|int=None) -> types.Message:
        reply_markup = reply_markup or self.get_available_buttonset(chat_id)
        super().send_message(
            chat_id, text, parse_mode,entities, disable_web_page_preview,
            disable_notification, protect_content, reply_to_message_id,
            allow_sending_without_reply, reply_markup,
            timeout, message_thread_id
        )


tbot = CustomBot(TOKEN, state_storage=StateMemoryStorage())
tbot.add_button_set(AdminButtonSet)
tbot.add_button_set(UserButtonSet)
