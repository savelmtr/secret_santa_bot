from telebot.types import Message, KeyboardButton, ReplyKeyboardMarkup, MessageEntity
from abc import ABC, abstractmethod
from telebot.async_telebot import AsyncTeleBot, REPLY_MARKUP_TYPES


class AbstractButton(ABC, KeyboardButton):
    name: str

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(AbstractButton, cls).__new__(cls)
        return cls.instance

    def __init__(self, bot: AsyncTeleBot):
        super().__init__(self.name)
        self.bot = bot

    @abstractmethod
    async def run(self, message: Message):
        pass


class AbstractButtonSet(ABC, ReplyKeyboardMarkup):
    resize_keyboard: bool = True
    buttons: tuple[tuple[AbstractButton]]

    def __init__(self, bot: AsyncTeleBot):
        super().__init__(resize_keyboard=self.resize_keyboard)
        for row in self.buttons:
            self.row(*[b(bot) for b in row])

    @abstractmethod
    async def is_available(self, message: Message):
        pass


class CustomBot(AsyncTeleBot):

    def __init__(self, *args, **kwargs):
        async def process_button_press(message: Message):
            btnset = await self.get_available_buttonset(message.chat.id)
            if not btnset:
                return
            for btn in (b for row in btnset.buttons for b in row):
                if message.text == btn.name:
                    await btn(self).run(message)
                    return

        super().__init__(*args, **kwargs)
        self.button_sets = []
        self.message_handler(content_types=['text'])(process_button_press)


    def add_button_set(self, button_set: AbstractButtonSet):
        self.button_sets.append(button_set(self))


    async def get_available_buttonset(self, chat_id: int | str):
        available_bs = [
            bs for bs in self.button_sets if (await bs.is_available(chat_id))
        ]
        return available_bs[0] if available_bs else None

    async def send_message(
            self, chat_id: int | str, text: str, 
            parse_mode:  None | str=None, 
            entities:  None|list[MessageEntity]=None,
            disable_web_page_preview:  None|bool=None, 
            disable_notification:  None|bool=None, 
            protect_content:  None|bool=None,
            reply_to_message_id:  None|int=None, 
            allow_sending_without_reply:  None|bool=None,
            reply_markup:  None|REPLY_MARKUP_TYPES=None,
            timeout:  None|int=None,
            message_thread_id:  None|int=None) -> Message:
        if message_thread_id:
            raise NotImplemented('message_thread_id')
        reply_markup = reply_markup or await self.get_available_buttonset(chat_id)
        await super().send_message(
            chat_id, text, parse_mode, entities, disable_web_page_preview,
            disable_notification, protect_content, reply_to_message_id,
            allow_sending_without_reply, reply_markup,
            timeout
        )

    def add_message_handler(self, handler_dict: dict):
        if self.message_handlers:
            self.message_handlers.insert(-1, handler_dict)
        else:
            self.message_handlers.append(handler_dict)
