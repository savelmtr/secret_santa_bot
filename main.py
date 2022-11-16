import re
from telebot.async_telebot import AsyncTeleBot
import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker


NUM_PTTRN = re.compile(r'\d+')
TOKEN = os.getenv('TOKEN')
engine = create_async_engine(
    os.getenv('PG_URI'),
    echo=False,
)
async_session = async_sessionmaker(engine, expire_on_commit=False)
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


** Следующие операции может осуществлять только создатель комнаты **

* /lock пароль -- установить пароль для присоединения к комнате.
По умолчанию комната не защищена от присоединения к ней людей.
Чтобы случайные люди не имели возможности испортить ваш уютный междусобойчик,
их можно "запирать" паролем. Чтобы сбросить пароль введите /lock.

* /members -- посмотреть список участников комнаты. 

* /set_pairs -- сгенерировать дарительные пары.

* /reset -- удалить всех участников из комнаты.

* /rename -- переименовать комнату.
\
""")


@bot.message_handler(commands=['start'])
async def get_room(message):
    #    print(message.from_user.id, message.from_user.username)
    payload = message.text[6:]
    if not payload:
        await bot.reply_to(message, 'Вы не ввели ни номера комнаты, ни названия новой комнаты. Для справки /help.')
    elif NUM_PTTRN.match(payload):
        await bot.reply_to(message, f'Вы присоединились к комнате {payload}')
    else:
        async with async_session() as session:
            async with session.begin():
                pass
        await bot.reply_to(message, f'Вы создали комнату {payload}')


asyncio.run(bot.polling())
