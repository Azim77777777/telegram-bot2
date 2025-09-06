
# ggbot_final.py
import asyncio
import random
import time
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# -------- CONFIG ----------
TOKEN = "8479187561:AAFDt_mqBGySDVZwJO0ZoaaqNq5-yG27Mvk"   # <- вставь токен
ADMINS = [123456789]       # <- вставь свой Telegram ID(ы)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# --------- DATABASE ----------
conn = sqlite3.connect("ggbot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    status TEXT DEFAULT ' ',
    bonus_time INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS promos(
    name TEXT PRIMARY KEY,
    amount INTEGER,
    uses_left INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    game TEXT,
    stake INTEGER,
    result TEXT,
    amount INTEGER,
    ts INTEGER
)
""")
conn.commit()

# --------- HELPERS ----------
def is_admin(uid: int) -> bool:
    return uid in ADMINS

def get_user(uid: int):
    cursor.execute("SELECT id, username, balance, status, bonus_time FROM users WHERE id=?", (uid,))
    return cursor.fetchone()

def ensure_user(uid: int, username: str = None):
    if not get_user(uid):
        cursor.execute("INSERT INTO users (id, username, balance) VALUES (?, ?, ?)", (uid, username or "Игрок", 0))
        conn.commit()

def get_balance(uid: int) -> int:
    u = get_user(uid)
    return u[2] if u else 0

def set_balance(uid: int, val: int):
    cursor.execute("UPDATE users SET balance=? WHERE id=?", (val, uid))
    conn.commit()

def add_balance(uid: int, delta: int):
    bal = get_balance(uid) + delta
    set_balance(uid, bal)
    return bal

def set_status(uid: int, status: str):
    cursor.execute("UPDATE users SET status=? WHERE id=?", (status, uid))
    conn.commit()

def add_history(user_id: int, game: str, stake: int, result: str, amount: int):
    cursor.execute("INSERT INTO history (user_id, game, stake, result, amount, ts) VALUES (?, ?, ?, ?, ?, ?)",
                   (user_id, game, stake, result, amount, int(time.time())))
    conn.commit()

def format_report(stake:int, loss:int, outcome:str, balance:int, win:int=None):
    if win and win>0:
        return (f"💸 Ставка: {stake}\n"
                f"🎟 Выигрыш: {win}\n"
                f"📈 Выпало: {outcome}\n"
                f"💰 Баланс: {balance}")
    else:
        return (f"💸 Ставка: {stake}\n"
                f"🎟 Проигрыш: {loss}\n"
                f"📈 Выпало: {outcome}\n"
                f"💰 Баланс: {balance}")

# --------- IN-MEMORY GAMES ----------
games_miner = {}
games_crash = {}
duel_requests = {}
games_tower = {}

# --------- COMMANDS: REG / PROFILE / BONUS / TRANSFER ----------
@dp.message_handler(commands=['start'])
async def start_cmd(m: types.Message):
    if get_user(m.from_user.id):
        await m.answer("Вы уже зарегистрированы. /meb — профиль")
    else:
        await m.answer("Привет! Я GG BOT | FEZ. Для регистрации используйте /ss")

@dp.message_handler(commands=['ss'])
async def ss_cmd(m: types.Message):
    uid = m.from_user.id
    uname = m.from_user.username or m.from_user.full_name or "Игрок"
    if get_user(uid):
        await m.answer("Вы уже зарегистрированы.")
        return
    cursor.execute("INSERT INTO users (id, username, balance) VALUES (?, ?, ?)", (uid, uname, 0))
    conn.commit()
    await m.answer(f"Регистрация успешна. Добро пожаловать, {uname}! Баланс: 0")

@dp.message_handler(commands=['meb', 'я'])
async def meb_cmd(m: types.Message):
    u = get_user(m.from_user.id)
    if not u:
        await m.answer("Вы не зарегистрированы. /ss")
        return
    await m.answer(f"👤 {u[1]}\n💰 Баланс: {u[2]}\n🏅 Статус: {u[3]}")

@dp.message_handler(commands=['бонус'])
async def bonus_cmd(m: types.Message):
    uid = m.from_user.id
    u = get_user(uid)
    if not u:
        await m.answer("Вы не зарегистрированы. /ss")
        return
    now = int(time.time())
    if u[4] and now - u[4] < 3600:
        await m.answer("Бонус можно получать раз в 1 час.")
        return
    amt = random.randint(5000, 50000)
    new = add_balance(uid, amt)
    cursor.execute("UPDATE users SET bonus_time=? WHERE id=?", (now, uid)); conn.commit()
    await m.answer(f"💰 Вы получили бонус: {amt}\n💰 Баланс: {new}")

@dp.message_handler(commands=['перевести', 'transfer'])
async def transfer_cmd(m: types.Message):
    parts = m.get_args().split()
    if len(parts) != 2:
        await m.answer("Использование: /перевести <сумма> <айди>")
        return
    try:
        amount = int(parts[0]); target = int(parts[1])
    except:
        await m.answer("Аргументы: /перевести <сумма> <айди> (числа)")
        return
    uid = m.from_user.id
    if get_balance(uid) < amount:
        await m.answer("Недостаточно средств.")
        return
    if not get_user(target):
        await m.answer("Получатель не зарегистрирован.")
        return
    set_balance(uid, get_balance(uid)-amount)
    add_balance(target, amount)
    await m.answer(f"Перевод успешен. Вы перевели {amount} пользователю {target}. Баланс: {get_balance(uid)}")

# --------- PROMOCODE / ADMIN ----------
@dp.message_handler(commands=['new_promo'])
async def new_promo_cmd(m: types.Message):
    if not is_admin(m.from_user.id):
        await m.answer("Нет доступа.")
        return
    parts = m.get_args().split()
    if len(parts) != 3:
        await m.answer("Использование: /new_promo <name> <amount> <uses>")
        return
    name = parts[0]
    try:
        amount = int(parts[1]); uses = int(parts[2])
    except:
        await m.answer("amount и uses — числа.")
        return
    try:
        cursor.execute("INSERT INTO promos (name, amount, uses_left) VALUES (?, ?, ?)", (name, amount, uses))
        conn.commit()
        await m.answer(f"Промокод {name} создан: {amount} (активаций: {uses})")
    except sqlite3.IntegrityError:
        await m.answer("Промокод с таким именем уже есть.")

@dp.message_handler(commands=['pr'])
async def pr_cmd(m: types.Message):
    name = m.get_args().strip()
    if not name:
        await m.answer("Использование: /pr <name>")
        return
    cursor.execute("SELECT amount, uses_left FROM promos WHERE name=?", (name,))
    row = cursor.fetchone()
    if not row:
        await m.answer("Промокод не найден.")
        return
    amount, uses = row
    if uses <= 0:
        await m.answer("Активации кончились.")
        return
    new = add_balance(m.from_user.id, amount)
    cursor.execute("UPDATE promos SET uses_left=? WHERE name=?", (uses-1, name)); conn.commit()
    await m.answer(f"✅ Промокод активирован. Вы получили {amount}\n💰 Баланс: {new}")

@dp.message_handler(commands=['give_money'])
async def give_money_cmd(m: types.Message):
    if not is_admin(m.from_user.id):
        await m.answer("Нет доступа.")
        return
    parts = m.get_args().split()
    if len(parts)!=2:
        await m.answer("Использование: /give_money <id> <sum>")
        return
    try:
        tid = int(parts[0]); amt = int(parts[1])
    except:
        await m.answer("Аргументы должны быть числа.")
        return
    if not get_user(tid):
        await m.answer("Пользователь не найден.")
        return
    new = add_balance(tid, amt)
    await m.answer(f"Выдано {amt} пользователю {tid}. Баланс: {new}")

@dp.message_handler(commands=['give_status'])
async def give_status_cmd(m: types.Message):
    if not is_admin(m.from_user.id):
        await m.answer("Нет доступа.")
        return
    parts = m.get_args().split()
    if len(parts)!=2:
        await m.answer("Использование: /give_status <id> <status>")
        return
    try:
        tid = int(parts[0]); status = parts[1]
    except:
        await m.answer("Аргументы неверны.")
        return
    if not get_user(tid):
        await m.answer("Пользователь не найден.")
        return
    set_status(tid, status)
    await m.answer(f"Пользователю {tid} присвоен статус: {status}")

# --------- MINER ----------
@dp.message_handler(commands=['miner'])
async def miner_cmd(m: types.Message):
    parts = m.get_args().strip()
    if not parts.isdigit():
        await m.answer("Использование: /miner <ставка>")
        return
    stake = int(parts)
    uid = m.from_user.id
    u = get_user(uid)
    if not u:
        await m.answer("Вы не зарегистрированы.")
        return
    if stake <= 0 or stake > u[2]:
        await m.answer("Неверная ставка или недостаточно средств.")
        return
    set_balance(uid, u[2]-stake)
    bombs = set(random.sample(range(25), 3))
    cells = [-1 if i in bombs else 0 for i in range(25)]
    games_miner[uid] = {'cells':cells, 'stake':stake, 'win':0, 'opened':set(), 'chat':m.chat.id, 'msg':None}
    kb = InlineKeyboardMarkup(row_width=5)
    for i in range(25):
        kb.insert(InlineKeyboardButton("❔", callback_data=f"mine_{i}_{uid}"))
    sent = await m.answer(f"💸 Ставка: {stake}\n💰 Баланс: {get_balance(uid)}\n📈 Откройте клетку:", reply_markup=kb)
    games_miner[uid]['msg'] = (sent.chat.id, sent.message_id)

@dp.callback_query_handler(lambda c: c.data.startswith("mine_"))
async def mine_click_cb(c: types.CallbackQuery):
    parts = c.data.split('_'); idx = int(parts[1]); uid = int(parts[2])
    if c.from_user.id != uid:
        await c.answer("Это не ваша игра.", show_alert=True); return
    game = games_miner.get(uid)
    if not game:
        await c.answer("Игра не найдена."); return
    if idx in game['opened']:
        await c.answer("Уже открыто."); return
    game['opened'].add(idx)
    if game['cells'][idx] == -1:
        stake = game['stake']
        bal = get_balance(uid)
        await c.message.edit_text(format_report(stake, stake, "💣 Бомба", bal))
        add_history(uid, "miner", stake, "bomb", -stake)
        del games_miner[uid]
        return
    coeff = random.randint(1,50)
    gain = game['stake'] * coeff
    game['win'] += gain
    bal = get_balance(uid)
    kb = InlineKeyboardMarkup(row_width=5)
    for i in range(25):
        if i in game['opened']:
            kb.insert(InlineKeyboardButton("✅", callback_data=f"mine_{i}_{uid}"))
        else:
            kb.insert(InlineKeyboardButton("❔", callback_data=f"mine_{i}_{uid}"))
    await c.message.edit_text(f"💸 Ставка: {game['stake']}\n📈 Клетка {idx+1}: ✅ Коэффициент {coeff}\n💰 Текущий выигрыш: {game['win']}\n💰 Баланс: {bal}", reply_markup=kb)
    kb2 = InlineKeyboardMarkup().add(InlineKeyboardButton("💰 Забрать", callback_data=f"mine_take_{uid}"))
    await c.message.answer("Можете забрать выигрыш:", reply_markup=kb2)

@dp.callback_query_handler(lambda c: c.data.startswith("mine_take_"))
async def mine_take_cb(c: types.CallbackQuery):
    uid = int(c.data.split('_')[-1])
    if c.from_user.id != uid:
        await c.answer("Это не ваша игра.", show_alert=True); return
    game = games_miner.get(uid)
    if not game:
        await c.answer("Игра не найдена."); return
    win = game['win']
    new_bal = add_balance(uid, win)
    await c.message.edit_text(format_report(game['stake'], 0, f"Клетки открыты: {len(game['opened'])}", new_bal, win=win))
    add_history(uid, "miner", game['stake'], "cashout", win)
    del games_miner[uid]

# --------- CRASH ----------
async def crash_runner(uid):
    game = games_crash.get(uid)
    if not game:
        return
    chat, msg = game['msg']
    coef = 1.0
    crash_point = random.uniform(1.2, 40.0)
    game['current'] = coef
    try:
        while game.get('active') and not game.get('cashed'):
            coef += round(random.uniform(0.05, 0.7), 2)
            game['current'] = round(coef,2)
            try:
                await bot.edit_message_text(chat_id=chat, message_id=msg,
                    text=f"💸 Ставка: {game['stake']}\n📈 Коэффициент: {game['current']}x\n💰 Баланс: {get_balance(uid)}",
                    reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("💰 Забрать", callback_data=f"crash_take_{uid}")))
            except:
                pass
            if game['current'] >= crash_point:
                game['active'] = False
                if not game.get('cashed'):
                    await bot.edit_message_text(chat_id=chat, message_id=msg,
                        text=format_report(game['stake'], game['stake'], f"Взорвало на {round(crash_point,2)}x", get_balance(uid)))
                    add_history(uid, "crash", game['stake'], f"crashed@{round(crash_point,2)}x", -game['stake'])
                break
            await asyncio.sleep(1)
    finally:
        games_crash.pop(uid, None)

@dp.message_handler(commands=['crash'])
async def crash_cmd(m: types.Message):
    parts = m.get_args().strip()
    if not parts.isdigit():
        await m.answer("Использование: /crash <ставка>")
        return
    stake = int(parts); uid = m.from_user.id
    u = get_user(uid)
    if not u or stake<=0 or stake>u[2]:
        await m.answer("Проверьте регистрацию/баланс.")
        return
    set_balance(uid, u[2]-stake)
    sent = await m.answer(f"💸 Ставка: {stake}\n📈 Коэффициент: 1.00x\n💰 Баланс: {get_balance(uid)}",
                          reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("💰 Забрать", callback_data=f"crash_take_{uid}")))
    games_crash[uid] = {'stake':stake, 'active':True, 'current':1.0, 'cashed':False, 'msg':(sent.chat.id, sent.message_id)}
    asyncio.create_task(crash_runner(uid))

@dp.callback_query_handler(lambda c: c.data.startswith("crash_take_"))
async def crash_take_cb(c: types.CallbackQuery):
    uid = int(c.data.split('_')[-1])
    if c.from_user.id != uid:
        await c.answer("Это не ваша игра.", show_alert=True); return
    game = games_crash.get(uid)
    if not game: await c.answer("Игра не найдена."); return
    if game.get('cashed'): await c.answer("Вы уже забрали."); return
    coef = game.get('current',1.0)
    stake = game['stake']
    win = int(stake * coef)
    new_bal = add_balance(uid, win)
    game['cashed'] = True; game['active'] = False
    await bot.edit_message_text(chat_id=game['msg'][0], message_id=game['msg'][1],
                               text=format_report(stake, 0, f"{coef}x", new_bal, win=win))
    add_history(uid, "crash", stake, f"cashout@{coef}x", win)
    games_crash.pop(uid, None)

# --------- ROULETTE ----------
def red_numbers():
    return {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

@dp.message_handler(commands=['rul','roulette'])
async def rul_cmd(m: types.Message):
    parts = m.get_args().split()
    if len(parts)<2:
        await m.answer("Использование: /rul <ставка> <число(0-36)|red|black|even|odd>")
        return
    try:
        stake = int(parts[0])
    except:
        await m.answer("Ставка должна быть числом."); return
    choice = parts[1].lower()
    uid = m.from_user.id
    u = get_user(uid)
    if not u or stake<=0 or stake>u[2]:
        await m.answer("Проверьте регистрацию/баланс."); return
    set_balance(uid, u[2]-stake)
    num = random.randint(0,36)
    color = 'green' if num==0 else ('red' if num in red_numbers() else 'black')
    parity = 'zero' if num==0 else ('even' if num%2==0 else 'odd')
    win = 0
    if choice.isdigit():
        if int(choice)==num:
            win = stake * 36
    elif choice in ('red','black'):
        if color==choice:
            win = stake * 2
    elif choice in ('even','odd'):
        if parity==choice:
            win = stake * 2
    new_bal = get_balance(uid)
    if win:
        new_bal = add_balance(uid, win)
        add_history(uid, "roulette", stake, f"{num}({color},{parity})", win)
        await m.answer(format_report(stake, 0, f"{num} ({color}, {parity})", new_bal, win=win))
    else:
        add_history(uid, "roulette", stake, f"{num}({color},{parity})", -stake)
        await m.answer(format_report(stake, stake, f"{num} ({color}, {parity})", new_bal))

# --------- DICE ----------
@dp.message_handler(commands=['кости','dice'])
async def dice_cmd(m: types.Message):
    parts = m.get_args().split()
    if len(parts) < 2:
        await m.answer("Использование: /dice <ставка> <number/over/under> [val]"); return
    try:
        stake = int(parts[0])
    except:
        await m.answer("Ставка должна быть числом."); return
    typ = parts[1].lower()
    uid = m.from_user.id
    u = get_user(uid)
    if not u or stake<=0 or stake>u[2]:
        await m.answer("Проверьте регистрацию/баланс."); return
    set_balance(uid, u[2]-stake)
    roll = random.randint(1,6)
    win = 0
    if typ == 'number':
        if len(parts)<3:
            await m.answer("Укажите число 1-6."); add_balance(uid, stake); return
        val = int(parts[2])
        if val==roll:
            win = stake * 6
    elif typ == 'over':
        val = int(parts[2]) if len(parts)>=3 else 3
        if roll > val:
            win = int(stake * 1.5)
    elif typ == 'under':
        val = int(parts[2]) if len(parts)>=3 else 3
        if roll < val:
            win = int(stake * 1.5)
    else:
        await m.answer("Тип: number/over/under"); add_balance(uid, stake); return
    if win:
        new = add_balance(uid, win)
        add_history(uid, "dice", stake, f"roll:{roll}", win)
        await m.answer(format_report(stake, 0, f"{roll}", new, win=win))
    else:
        add_history(uid, "dice", stake, f"roll:{roll}", -stake)
        await m.answer(format_report(stake, stake, f"{roll}", get_balance(uid)))

# --------- DUEL ----------
@dp.message_handler(commands=['дуэль','duel'])
async def duel_cmd(m: types.Message):
    parts = m.get_args().split()
    if len(parts)!=2:
        await m.answer("Использование: /duel <айди> <ставка>"); return
    try:
        target = int(parts[0]); stake = int(parts[1])
    except:
        await m.answer("Аргументы: числа"); return
    uid = m.from_user.id
    if target==uid:
        await m.answer("Нельзя вызвать себя."); return
    if not get_user(target) or not get_user(uid):
        await m.answer("Один из игроков не зарегистрирован."); return
    if get_balance(uid) < stake or get_balance(target) < stake:
        await m.answer("Недостаточно средств у одного из игроков."); return
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Принять дуэль", callback_data=f"duel_accept_{uid}_{target}_{stake}"))
    sent = await m.reply(f"Дуэль: {uid} вызывает {target} на {stake}.", reply_markup=kb)
    duel_requests[uid] = {'target':target, 'stake':stake, 'msg':(sent.chat.id, sent.message_id)}

@dp.callback_query_handler(lambda c: c.data.startswith("duel_accept_"))
async def duel_accept_cb(c: types.CallbackQuery):
    parts = c.data.split('_'); challenger = int(parts[2]); target = int(parts[3]); stake = int(parts[4])
    accepter = c.from_user.id
    if accepter != target:
        await c.answer("Вы не можете принять этот вызов.", show_alert=True); return
    req = duel_requests.get(challenger)
    if not req or req['target']!=target or req['stake']!=stake:
        await c.answer("Запрос недействителен."); return
    if get_balance(challenger) < stake or get_balance(target) < stake:
        await c.answer("Недостаточно средств."); return
    set_balance(challenger, get_balance(challenger)-stake)
    set_balance(target, get_balance(target)-stake)
    winner = random.choice([challenger, target])
    add_balance(winner, stake*2)
    await c.message.edit_text(f"💸 Ставка: {stake}\n📈 Победитель: {winner}\n💰 Баланс: {get_balance(winner)}")
    add_history(winner, "duel", stake, f"won_vs_{challenger if winner==target else target}", stake*2)
    duel_requests.pop(challenger, None)

# --------- TOWER ----------
@dp.message_handler(commands=['tower','башня'])
async def tower_cmd(m: types.Message):
    parts = m.get_args().strip()
    if not parts.isdigit():
        await m.answer("Использование: /tower <ставка>"); return
    stake = int(parts); uid = m.from_user.id
    u = get_user(uid)
    if not u or stake<=0 or stake>u[2]:
        await m.answer("Проверьте регист
    
