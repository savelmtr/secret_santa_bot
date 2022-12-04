class CALLBACK_TEXTS:
    welcome = '''Хо-хоу-хоу! 🎅

На улице выпал первый снег, а значит, что близится Новый год! 🎆
Добро пожаловать в бот-помощник тайного Деда Мороза.

С помощью этого бота вы можете:
1️⃣ создать комнату или присоединиться к уже созданной;
2️⃣ составить свой список желаний для Вашего тайного Деда Мороза;
3️⃣ сформировать пары участников.
    
Также, в любой момент Вы можете изменить свои данные: пожелания, имя и фамилию.
Чтобы начать собственную игру, нажмите кнопку "Создать комнату", а если хотите присоединиться, то "Подключиться к комнате"
    '''
    
    greeting = """Хоу-хоу-хоу 🎅

Вот и начинается сезон игры в тайного Деда Мороза 😀

    """

    connection_room = """Ох-хоу-хоу 🎅
    
Введи номер комнаты, к которой хочешь присоединиться"""

    connect_to_room = """Ты присоединился к комнате Санты 🎅🏼 {room_name}. 
    
Напиши свои Имя и Фамилию чтобы я внес тебя в список участников! 😇"""
    wish_message = """Еще чуть-чуть и я добавлю тебя в комнату.
    
Осталось написать свой список желаний (все желания одним сообщением), чтобы твой дед мороз знал, что тебе дарить.
Но учти, что капитан твоей комнаты поставил ограничение по бюджету на подарок: {max_price} 💸"""
    congratulations = """Ура! Ты просоединился к комнате {room}!
    
Список твоих желаний: {my_wishes} 🎁
В комнате ты представлен как: @{username} ({first_name} {last_name})"""
    update = """Дед Мороз обновил твои данные! 📋
    
Список твоих желаний: {my_wishes} 🎁
В комнате ты представлен как: @{username} ({first_name} {last_name})"""
    info = """Ты находишься в комнате {room} 
    
Список твоих желаний: {my_wishes} 🎁
В комнате ты представлен как: @{username} ({first_name} {last_name})"""
    link = "Вот ссылка для приглашения участников в комнату {room_name} \n" \
           "https://t.me/{bot_name}/?start={room_id}"

    pairs_data = """Хоу-хоу-хоу. Я нашёл тебе деда мороза🎅

В свою очередь, ты будешь дедом морозом для @{username} ({first_name} {last_name})

Список желаний: {wishes}🎁"""