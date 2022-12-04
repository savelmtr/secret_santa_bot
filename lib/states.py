from telebot.asyncio_handler_backends import State, StatesGroup


class States(StatesGroup):
    connect_room = State()
    create_room = State()
    user_name = State()
    wish_list = State()
    update_name = State()
    update_wishes = State()
    create_password = State()
    enter_password = State()
    max_price = State()
    rename = State()
