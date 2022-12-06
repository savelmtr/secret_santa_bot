import asyncio
import os

from telebot import asyncio_filters
from telebot.asyncio_storage import StateMemoryStorage

from lib.base import CustomBot
from lib.buttons import AdminButtonSet, UserButtonSet
from lib.handlers import (callback_query, connect_room,
                          create_password_handler, create_room_handler,
                          enter_max_price, entering_to_room, get_room,
                          get_user_name, get_user_wishes, try_rename_room,
                          update_name, update_wishes)
from lib.states import States


TOKEN = os.getenv('TOKEN')

bot = CustomBot(TOKEN, state_storage=StateMemoryStorage())
bot.add_button_set(AdminButtonSet)
bot.add_button_set(UserButtonSet)
bot.add_custom_filter(asyncio_filters.StateFilter(bot))


bot.message_handler(state=States.update_name)(update_name)
bot.message_handler(state=States.update_wishes)(update_wishes)
bot.message_handler(state=States.create_room)(create_room_handler)
bot.callback_query_handler(func=lambda call: 'room' in call.data)(callback_query)
bot.message_handler(state=States.create_password)(create_password_handler)
bot.message_handler(state=States.connect_room)(connect_room)
bot.message_handler(state=States.enter_password)(entering_to_room)
bot.message_handler(state=States.user_name)(get_user_name)
bot.message_handler(state=States.wish_list)(get_user_wishes)
bot.message_handler(state=States.max_price)(enter_max_price)
bot.message_handler(commands=['start'])(get_room)
bot.message_handler(state=States.rename)(try_rename_room)


if __name__ == '__main__':
    asyncio.run(bot.polling())
