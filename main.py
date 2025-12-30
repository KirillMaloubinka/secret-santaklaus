import asyncio
import sqlite3
import random

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

API_TOKEN = "8297013662:AAHfwfotUft7RHovetEFGg3mWSNBLr410wg"
ADMIN_ID = 8500766185
BOT_USERNAME = "santa_kristeam_bot"

bot = Bot(API_TOKEN)
dp = Dispatcher()

# ===== БАЗА =====
db = sqlite3.connect("santa.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS participants (
    chat_id INTEGER,
    user_id INTEGER,
    username TEXT,
    PRIMARY KEY (chat_id, user_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS blocked_users (
    user_id INTEGER PRIMARY KEY
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS santa_pairs (
    chat_id INTEGER,
    giver_id INTEGER,
    receiver_id INTEGER,
    PRIMARY KEY (chat_id, giver_id)
)
""")

db.commit()

# ===== FSM =====
class BlockUserState(StatesGroup):
    waiting_user = State()

# ===== КНОПКИ =====
def get_join_keyboard(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎁 Участвовать",
                url=f"https://t.me/{BOT_USERNAME}?start=join_{chat_id}"
            )
        ],
        [InlineKeyboardButton(text="🚪 Выйти из игры", callback_data="leave")]
    ])

def get_admin_keyboard(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список", callback_data="list")],
        [InlineKeyboardButton(text="👥 Кол-во", callback_data="count")],
        [InlineKeyboardButton(text="🚫 Заблокировать игрока", callback_data="block_user")],
        [InlineKeyboardButton(text="🎁 Запуск Санты", callback_data="start_santa")],
        [InlineKeyboardButton(text="♻️ Сброс", callback_data="reset")],
        [InlineKeyboardButton(text="🔗 Ссылка", callback_data="send_link")]
    ])

# ===== /start =====
@dp.message(CommandStart())
async def start(message: Message):
    if message.chat.type == "private":
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            await message.answer(
                "🎄 Тайный Санта\n\n"
                "Перейдите по ссылке из группы, чтобы участвовать 🎁"
            )
            return

        payload = args[1]
        if not payload.startswith("join_"):
            return

        chat_id = int(payload.replace("join_", ""))
        user = message.from_user
        username = f"@{user.username}" if user.username else user.full_name

        cur.execute("SELECT 1 FROM blocked_users WHERE user_id=?", (user.id,))
        if cur.fetchone():
            await message.answer("🚫 Вы заблокированы и не можете участвовать.")
            return

        cur.execute(
            "INSERT OR IGNORE INTO participants (chat_id, user_id, username) VALUES (?, ?, ?)",
            (chat_id, user.id, username)
        )
        db.commit()

        await message.answer(
            "🎉 Вы зарегистрированы в Тайном Санте!\n\n"
            "Ожидайте запуска 🎁"
        )
        return

    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    is_admin = member.is_chat_admin()

    await message.answer(
        "🎄 Тайный Санта\n\n"
        "Нажмите кнопку ниже 👇",
        reply_markup=get_admin_keyboard(message.chat.id) if is_admin else get_join_keyboard(message.chat.id)
    )

# ===== ADMIN =====
@dp.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return

    await message.answer("👑 Панель администратора", reply_markup=get_admin_keyboard(message.chat.id))

# ===== CALLBACKS =====
@dp.callback_query(F.data == "list")
async def list_users(call: CallbackQuery):
    cur.execute("SELECT username FROM participants WHERE chat_id=?", (call.message.chat.id,))
    users = cur.fetchall()
    text = "\n".join(u[0] for u in users) if users else "Список пуст"
    await call.message.answer(text)
    await call.answer()

@dp.callback_query(F.data == "count")
async def count_users(call: CallbackQuery):
    cur.execute("SELECT COUNT(*) FROM participants WHERE chat_id=?", (call.message.chat.id,))
    count = cur.fetchone()[0]
    await call.message.answer(f"👥 Участников: {count}")
    await call.answer()

# ===== ЗАПУСК САНТЫ =====
@dp.callback_query(F.data == "start_santa")
async def start_santa(call: CallbackQuery):
    chat_id = call.message.chat.id

    cur.execute(
        "SELECT user_id, username FROM participants WHERE chat_id=?",
        (chat_id,)
    )
    users = cur.fetchall()

    if len(users) < 2:
        await call.message.answer("❌ Нужно минимум 2 участника")
        await call.answer()
        return

    random.shuffle(users)

    cur.execute("DELETE FROM santa_pairs WHERE chat_id=?", (chat_id,))
    db.commit()

    for i in range(len(users)):
        giver_id, giver_name = users[i]
        receiver_id, receiver_name = users[(i + 1) % len(users)]

        cur.execute(
            "INSERT INTO santa_pairs (chat_id, giver_id, receiver_id) VALUES (?, ?, ?)",
            (chat_id, giver_id, receiver_id)
        )

        try:
            await bot.send_message(
                giver_id,
                f"🎅 Тайный Санта!\n\n"
                f"🎁 Ты даришь подарок: {receiver_name}\n\n"
                f"Никому не говори 🤫"
            )
        except Exception as e:
            print(f"❌ Не удалось отправить {giver_id}: {e}")

    db.commit()

    await call.message.answer("🎉 Тайный Санта успешно запущен!")
    await call.answer()

@dp.callback_query(F.data == "reset")
async def reset_game(call: CallbackQuery):
    cur.execute("DELETE FROM participants WHERE chat_id=?", (call.message.chat.id,))
    cur.execute("DELETE FROM santa_pairs WHERE chat_id=?", (call.message.chat.id,))
    db.commit()
    await call.message.answer("♻️ Игра очищена")
    await call.answer()

@dp.callback_query(F.data == "send_link")
async def send_link(call: CallbackQuery):
    chat_id = call.message.chat.id
    link = f"https://t.me/{BOT_USERNAME}?start=join_{chat_id}"
    await bot.send_message(chat_id, f"🎁 Регистрация:\n{link}")
    await call.answer("Готово")

# ===== БЛОКИРОВКА =====
@dp.callback_query(F.data == "block_user")
async def block_user_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    await call.message.answer("🚫 Введите @username или user_id:")
    await state.set_state(BlockUserState.waiting_user)
    await call.answer()

@dp.message(BlockUserState.waiting_user)
async def block_user_finish(message: Message, state: FSMContext):
    text = message.text.strip()

    if text.startswith("@"):
        cur.execute("SELECT user_id FROM participants WHERE username=?", (text,))
        row = cur.fetchone()
        if not row:
            await message.answer("❌ Пользователь не найден")
            return
        user_id = row[0]
    else:
        if not text.isdigit():
            await message.answer("❌ Введите @username или user_id")
            return
        user_id = int(text)

    cur.execute("INSERT OR IGNORE INTO blocked_users (user_id) VALUES (?)", (user_id,))
    cur.execute("DELETE FROM participants WHERE user_id=?", (user_id,))
    db.commit()

    await message.answer("🚫 Пользователь удалён и заблокирован")
    await state.clear()

# ===== ВЫХОД =====
@dp.callback_query(F.data == "leave")
async def leave_game(call: CallbackQuery):
    cur.execute(
        "DELETE FROM participants WHERE chat_id=? AND user_id=?",
        (call.message.chat.id, call.from_user.id)
    )
    db.commit()
    await call.answer("🚪 Вы вышли из игры")

# ===== ПРОСМОТР ПАР (ТОЛЬКО АДМИН, РАБОТАЕТ С АЙФОНА) =====
@dp.message(F.text == "/pairs")
async def show_pairs(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cur.execute("""
        SELECT 
            p1.username,
            p2.username
        FROM santa_pairs s
        JOIN participants p1 ON s.giver_id = p1.user_id
        JOIN participants p2 ON s.receiver_id = p2.user_id
    """)
    pairs = cur.fetchall()

    if not pairs:
        await message.answer("❌ Тайный Санта ещё не запущен")
        return

    text = "🎅 *Распределение Тайного Санты:*\n\n"
    for giver, receiver in pairs:
        text += f"🎁 {giver} → {receiver}\n"

    await message.answer(text, parse_mode="Markdown")

# ===== ЗАПУСК =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())