import logging
import sqlite3
import asyncio
import random
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Слово для регистрации
@dp.message_handler(lambda message: message.text.lower() in ["сс","ss","регистрация"])
async def register_text(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        await message.answer("✅ Вы зарегистрированы!\n💰 Ваш баланс: 1,000,000")
    else:
        await message.answer("Вы уже зарегистрированы!")

# Слово для старта
@dp.message_handler(lambda message: message.text.lower() in ["старт","start"])
async def start_text(message: types.Message):
    await message.answer(
        "Привет! Я бот, который поможет тебе играть в мины и добывать ресурсы.\nИспользуй /hb или 'список' для просмотра всех команд.",
        reply_markup=main_menu()
    )

# 🔑 Вставь сюда токен от BotFather
API_TOKEN = "8107743933:AAGRIImvxDpPXlXFwGtI_NMcG5u7kLT2VZ4"
ADMIN_ID = 7167501974

# 🔧 Логирование
logging.basicConfig(level=logging.INFO)

# 📂 База данных
conn = sqlite3.connect("gamebot.db")
cur = conn.cursor()

# Создание таблиц
cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 1000000,
    factories TEXT DEFAULT '',
    hidden INTEGER DEFAULT 0,
    ref_id INTEGER DEFAULT NULL
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS promo (
    code TEXT PRIMARY KEY,
    amount INTEGER,
    activations INTEGER
)""")
conn.commit()

# 🤖 Инициализация бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 📌 Хелперы
def get_user(user_id):
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return cur.fetchone()

# 📌 Конвертация сокращений
def parse_amount(text):
    text = text.lower()
    if "ккк" in text:
        return int(text.replace("ккк","000000000"))
    elif "кк" in text:
        return int(text.replace("кк","000000"))
    elif "к" in text:
        return int(text.replace("к","000"))
    else:
        return int(text)

# 📌 Регистрация
@dp.message_handler(commands=["ss"])
async def register(message: types.Message):
    if not get_user(message.from_user.id):
        cur.execute("INSERT INTO users (user_id) VALUES (?)", (message.from_user.id,))
        conn.commit()
        await message.answer("✅ Вы зарегистрированы!\n💰 Ваш баланс: 1,000,000")
    else:
        await message.answer("Вы уже зарегистрированы!")

# 📌 Профиль
@dp.message_handler(commands=["meb", "я"])
async def profile(message: types.Message):
    user = get_user(message.from_user.id)
    if user:
        if user[3] == 1 and message.from_user.id != ADMIN_ID:
            return await message.answer("Профиль скрыт.")
        await message.answer(
            f"👤 Ваш профиль\n\n💰 Баланс: {user[1]:,}\n🏭 Заводы: {user[2] or 'нет'}"
        )
    else:
        await message.answer("Сначала зарегистрируйтесь: /ss")

# 📌 Бонус
@dp.message_handler(commands=["бонус", "bonus"])
async def bonus(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return await message.answer("Сначала зарегистрируйтесь: /ss")
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (100000, message.from_user.id))
    conn.commit()
    await message.answer("🎁 Вы получили бонус: 100,000")
    
    # 📌 Заводы
factories_list = {
    "small": 1_000_000,
    "medium": 10_000_000,
    "big": 100_000_000,
    "ultra": 500_000_000
}

@dp.message_handler(commands=["buy_factory"])
async def buy_factory(message: types.Message):
    try:
        _, name = message.text.split()
    except:
        return await message.answer("Использование: /buy_factory small|medium|big|ultra")
    if name not in factories_list:
        return await message.answer("Такого завода нет")
    price = factories_list[name]
    user = get_user(message.from_user.id)
    if user[1] < price:
        return await message.answer("Недостаточно денег для покупки")
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, message.from_user.id))
    new_factories = (user[2] + "," + name) if user[2] else name
    cur.execute("UPDATE users SET factories = ? WHERE user_id = ?", (new_factories, message.from_user.id))
    conn.commit()
    await message.answer(f"🏭 Завод {name} куплен за {price:,}")

# 📌 Начисление прибыли от заводов (2%/час)
async def factory_income():
    while True:
        await asyncio.sleep(3600)  # 1 час
        cur.execute("SELECT * FROM users")
        users = cur.fetchall()
        for u in users:
            if not u[2]:
                continue
            factories = u[2].split(",")
            income = 0
            for f in factories:
                if f in factories_list:
                    income += int(factories_list[f] * 0.02)
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (income, u[0]))
        conn.commit()

# 📌 Снять прибыль с завода
@dp.message_handler(commands=["collect"])
async def collect_profit(message: types.Message):
    user = get_user(message.from_user.id)
    if not user or not user[2]:
        return await message.answer("У вас нет заводов")
    factories = user[2].split(",")
    total_income = 0
    for f in factories:
        if f in factories_list:
            total_income += int(factories_list[f] * 0.02)
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_income, user[0]))
    conn.commit()
    await message.answer(f"💰 Вы собрали {total_income:,} с заводов!")

# 📌 Мини-игры через ключевые слова
@dp.message_handler()
async def keywords_handler(message: types.Message):
    text = message.text.lower().replace(" ", "")
    
    # Конвертация сокращений
    def parse_value(s):
        s = s.lower()
        s = s.replace("ккк","000000000").replace("кк","000000").replace("к","000")
        return int(s)

    user = get_user(message.from_user.id)
    if not user:
        return await message.answer("Сначала зарегистрируйтесь: /ss")

    # ---- Мини
    if text.startswith("мини"):
        try:
            bet = parse_value(text.replace("мини",""))
            if user[1] < bet:
                return await message.answer("Недостаточно средств")
            if random.random() > 0.5:
                prize = bet * 2
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (prize, user[0]))
                conn.commit()
                await message.answer(f"🎲 Победа! Выигрыш: {prize:,}\n💰 Баланс: {user[1] + prize - bet:,}")
            else:
                cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user[0]))
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, ADMIN_ID))
                conn.commit()
                await message.answer(f"🎲 Проигрыш: {bet:,}\n💸 Деньги пошли владельцу!")
        except:
            await message.answer("Использование: мини <ставка> (например, мини 1к)")

    # ---- Рулетка
    elif text.startswith("рул"):
        try:
            parts = text.replace("рул","").split(",")
            bet = parse_value(parts[0])
            choice = parts[1] if len(parts)>1 else "чет"
            if user[1] < bet:
                return await message.answer("Недостаточно средств")
            number = random.randint(0,36)
            color = "красное" if number % 2 == 0 else "черное"
            parity = "чет" if number % 2 == 0 else "нечет"
            win = False
            coef = 2
            if choice.isdigit() and int(choice) == number:
                win, coef = True, 35
            elif choice in [color, parity]:
                win = True
            if win:
                prize = bet * coef
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (prize, user[0]))
                conn.commit()
                await message.answer(f"🎰 Выпало: {number} ({color}, {parity})\n✅ Победа! Выигрыш: {prize:,}")
            else:
                cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user[0]))
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, ADMIN_ID))
                conn.commit()
                await message.answer(f"🎰 Выпало: {number} ({color}, {parity})\n❌ Проигрыш: {bet:,}\n💸 Деньги пошли владельцу!")
        except:
            await message.answer("Использование: рул <ставка>,<цвет/чет/нечет> (например, рул 1к,красное)")

# 📌 Часть 2 завершена

# 📌 Краш
@dp.message_handler(lambda message: message.text.lower().startswith("краш"))
async def crash_game(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return await message.answer("Сначала зарегистрируйтесь: /ss")
    try:
        parts = message.text.lower().replace("краш","").split(",")
        bet = parse_amount(parts[0])
        coef = float(parts[1])
        if user[1] < bet:
            return await message.answer("Недостаточно средств")
        crash_coef = round(random.uniform(1,5),2)
        if crash_coef >= coef:
            prize = int(bet * coef)
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (prize, user[0]))
            conn.commit()
            await message.answer(f"💥 Краш достиг {crash_coef}x\n✅ Победа! Выигрыш: {prize:,}")
        else:
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user[0]))
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, ADMIN_ID))
            conn.commit()
            await message.answer(f"💥 Краш остановился на {crash_coef}x\n❌ Проигрыш: {bet:,}\n💸 Деньги пошли владельцу!")
    except:
        await message.answer("Использование: краш <ставка>,<коэф> (например, краш 1к,2.5)")

# 📌 Башня
@dp.message_handler(lambda message: message.text.lower().startswith("башня"))
async def tower_game(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return await message.answer("Сначала зарегистрируйтесь: /ss")
    try:
        parts = message.text.lower().replace("башня","").split(",")
        bet = parse_amount(parts[0])
        floors = int(parts[1])
        if user[1] < bet:
            return await message.answer("Недостаточно средств")
        coef = 1 + (floors * 0.2)
        if random.random() > 0.5:
            prize = int(bet * coef)
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (prize, user[0]))
            conn.commit()
            await message.answer(f"🏰 Победа! Этажей: {floors}, Выигрыш: {prize:,}")
        else:
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user[0]))
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, ADMIN_ID))
            conn.commit()
            await message.answer(f"🏰 Башня рухнула!\n❌ Проигрыш: {bet:,}\n💸 Деньги пошли владельцу!")
    except:
        await message.answer("Использование: башня <ставка>,<этажи> (например, башня 1кк,3)")

# 📌 Сейф
@dp.message_handler(lambda message: message.text.lower().startswith("сейф"))
async def safe_game(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        return await message.answer("Сначала зарегистрируйтесь: /ss")
    try:
        bet = parse_amount(message.text.lower().replace("сейф",""))
        if user[1] < bet:
            return await message.answer("Недостаточно средств")
        keys = [1,2,3,4]
        correct = random.choice(keys)
        chosen = random.choice(keys)
        if chosen == correct:
            prize = bet * 2
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (prize, user[0]))
            conn.commit()
            await message.answer(f"🔐 Вы угадали ключ! Выигрыш: {prize:,}")
        else:
            cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (bet, user[0]))
            cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bet, ADMIN_ID))
            conn.commit()
            await message.answer(f"🔐 Ошибка! Проигрыш: {bet:,}\n💸 Деньги пошли владельцу!")
    except:
        await message.answer("Использование: сейф <ставка> (например, сейф 1к)")

# 📌 Топ игроков
@dp.message_handler(commands=["топ","top"])
async def top_players(message: types.Message):
    cur.execute("SELECT user_id, balance FROM users WHERE hidden=0 ORDER BY balance DESC LIMIT 10")
    top = cur.fetchall()
    text = "🏆 ТОП игроков:\n\n"
    for i,u in enumerate(top,1):
        text += f"{i}. {u[0]} — {u[1]:,}₽\n"
    await message.answer(text)

# 📌 Админ: выдать/забрать деньги
@dp.message_handler(commands=["admin_money"])
async def admin_money(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, uid, amount = message.text.split()
        uid, amount = int(uid), int(amount)
    except:
        return await message.answer("Использование: /admin_money user_id сумма(+/-)")
    cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, uid))
    conn.commit()
    await message.answer(f"✅ Баланс пользователя {uid} изменён на {amount}")

# 📌 Админ: создать промокод
@dp.message_handler(commands=["new_promo"])
async def new_promo(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, code, amount, act = message.text.split()
        cur.execute("INSERT INTO promo VALUES (?, ?, ?)", (code, int(amount), int(act)))
        conn.commit()
        await message.answer(f"✅ Промокод {code} создан на {amount}₽ ({act} активаций)")
    except:
        await message.answer("Формат: /new_promo название сумма активации")
        
        # 📌 Главное меню
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🎮 Игры"), KeyboardButton("💰 Экономика"))
    kb.add(KeyboardButton("🛒 Маркет"), KeyboardButton("🏅 Статусы"))
    return kb

# 📌 Подменю с кнопкой Назад
def back_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("◀️ Назад"))
    return kb

# 📌 Команда /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "Привет! Я бот, который поможет тебе играть в мины и добывать ресурсы.\n\n"
        "Используй /hb или 'список' для просмотра всех команд.",
        reply_markup=main_menu()
    )

# 📌 Список команд /hb
@dp.message_handler(lambda message: message.text.lower() in ["hb","список"])
async def commands_list(message: types.Message):
    await message.answer(
        "📖 Меню команд\n─────────────────────\n"
        "⚙️ Основное\n"
        "/ss — Регистрация\n"
        "/meb или Я — Профиль\n"
        "Бонус — Бонус (каждые 1 час)\n"
        "/pr <название> — Активировать промокод\n"
        "/перевести <сумма> <айди> — Перевод\n"
        "/bb (1-9) или /купить (1-9) — Купить статус\n"
        "/топ или топ — Топ 10 игроков\n"
        "/hb или список — Список команд\n"
        "/new_promo [название] [сумма] [активаций] — Создать промокод\n"
        "/inv — Ваш инвентарь\n"
        "/market — Маркет\n"
        "/shop — Купить предмет\n"
        "реф — Ваша реф\n"
        "/st — Скрыть/открыть профиль в топе\n"
        "/farm — Фарминг",
        reply_markup=main_menu()
    )

# 📌 Обработка кнопок
@dp.message_handler(lambda message: message.text in ["🎮 Игры", "💰 Экономика", "🛒 Маркет", "🏅 Статусы", "◀️ Назад"])
async def menu_buttons(message: types.Message):
    if message.text == "🎮 Игры":
        await message.answer(
            "🎮 Игры\n────────────────\n"
            "рул или /rul <ставка>,<выбор> — Рулетка\n"
            "Кости <ставка>|<тип> — Игра в кости\n"
            "Минер <ставка> — Игра в мины\n"
            "Краш <ставка>,<коэф> — Игра краш\n"
            "Дуэль <ставка> — Дуэль между игроками\n"
            "Башня <ставка>,<этажи> — Игра в башню 🆕\n"
            "Сейф <ставка> — Игра в сейф 🆕\n",
            reply_markup=back_menu()
        )
    elif message.text == "💰 Экономика":
        await message.answer(
            "💰 Экономика / Сервисы\n──────────────────────────\n"
            "/pr <название> — Активировать промокод\n"
            "/перевести <сумма> <айди> — Перевод\n"
            "/bb (1-9) / /купить (1-9) — Купить статус\n"
            "/new_promo ... — Создать промокод\n"
            "/inv — Инвентарь\n"
            "/market, /shop — Маркет/Покупка\n"
            "реф — Ваша реф ссылка\n"
            "/топ — Топ игроков\n"
            "/st — Скрыть/открыть профиль\n"
            "/farm — Фарминг",
            reply_markup=back_menu()
        )
    elif message.text == "🛒 Маркет":
        await message.answer(
            "🛒 Маркет\n────────────────\n"
            "Используйте /market чтобы просмотреть магазин\n"
            "и /shop чтобы купить предмет.",
            reply_markup=back_menu()
        )
    elif message.text == "🏅 Статусы":
        await message.answer(
            "🏅 Статусы\n────────────────\n"
            '" " — начальный статус (0 💰)\n'
            '"👍" — 1к 💰\n'
            '"😀" — 25к 💰\n'
            '"🤯" — 100к 💰\n'
            '"😎" — 500к 💰\n'
            '"👽" — 2кк 💰\n'
            '"👾" — 7.5кк 💰\n'
            '"🤖" — 25кк 💰\n'
            '"👻" — 100кк 💰\n'
            '"👑" — 1ккк 💰\n'
            '"🎩" — 1кккк 💰\n'
            '"🎰" — 10кккк 💰\n'
            '"🎀" — Платный и эксклюзивный\n'
            '"🐍" — Платный и эксклюзивный\n'
            "/bb (1-11) - для приобретения статуса!",
            reply_markup=back_menu()
        )
    elif message.text == "◀️ Назад":
        await message.answer("Главное меню:", reply_markup=main_menu())

# 📌 Запуск бота
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(factory_income())
    executor.start_polling(dp, skip_updates=True)
    
