import asyncio
import sqlite3
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

API_TOKEN = "8297013662:AAHfwfotUft7RHovetEFGg3mWSNBLr410wg"
ADMIN_ID = 8500766185  # ← сюда вставь свой Telegram ID
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
db.commit()

# ===== КНОПКА С ССЫЛКОЙ =====
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

# ===== ПАНЕЛЬ АДМИНА =====
def get_admin_keyboard(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="/list", callback_data="list")],
        [InlineKeyboardButton(text="/count", callback_data="count")],
        [InlineKeyboardButton(text="/start_santa", callback_data="start_santa")],
        [InlineKeyboardButton(text="/reset", callback_data="reset")],
        [InlineKeyboardButton(text="Создать ссылку для чата", callback_data="send_link")]
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

        cur.execute(
            "INSERT OR IGNORE INTO participants (chat_id, user_id, username) VALUES (?, ?, ?)",
            (chat_id, user.id, username)
        )
        db.commit()

        await message.answer(
            "🎉 Вы успешно зарегистрированы в Тайном Санте!\n\n"
            "Ожидайте запуска 🎁"
        )
        return

    # В группе показываем кнопку для участников
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)
    is_admin = member.is_chat_admin()

    await message.answer(
        "🎄 Тайный Санта\n\n"
        "Нажмите кнопку ниже, чтобы участники могли зарегистрироваться 👇",
        reply_markup=get_join_keyboard(message.chat.id) if not is_admin else get_admin_keyboard(message.chat.id)
    )

# ===== /admin =====
@dp.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет доступа к панели администратора")
        return

    await message.answer(
        "👑 Панель администратора",
        reply_markup=get_admin_keyboard(message.chat.id)
    )

# ===== CALLBACKS АДМИНА =====
@dp.callback_query(F.data == "list")
async def list_users(call: CallbackQuery):
    chat_id = call.message.chat.id
    cur.execute("SELECT username FROM participants WHERE chat_id=?", (chat_id,))
    users = cur.fetchall()
    if users:
        await call.message.answer("📋 Список участников:\n" + "\n".join(u[0] for u in users))
    else:
        await call.message.answer("Список пуст")
    await call.answer()

@dp.callback_query(F.data == "count")
async def count_users(call: CallbackQuery):
    chat_id = call.message.chat.id
    cur.execute("SELECT COUNT(*) FROM participants WHERE chat_id=?", (chat_id,))
    count = cur.fetchone()[0]
    await call.message.answer(f"👥 Всего участников: {count}")
    await call.answer()

@dp.callback_query(F.data == "start_santa")
async def start_santa(call: CallbackQuery):
    chat_id = call.message.chat.id
    cur.execute("SELECT user_id, username FROM participants WHERE chat_id=?", (chat_id,))
    participants = cur.fetchall()

    if len(participants) < 2:
        await call.message.answer("⚠️ Нужно минимум 2 участника для Тайного Санты")
        await call.answer()
        return

    # Перемешиваем участников
    shuffled = participants[:]
    random.shuffle(shuffled)

    # Делаем распределение
    pairs = {}
    for i in range(len(shuffled)):
        giver = shuffled[i]
        receiver = shuffled[(i + 1) % len(shuffled)]
        pairs[giver[0]] = receiver[1]  # user_id -> username

    # Отправляем каждому личное сообщение
    for giver_id, receiver_username in pairs.items():
        try:
            await bot.send_message(giver_id, f"🎁 Привет! Твой тайный получатель подарка: {receiver_username}")
        except Exception as e:
            print(f"Не удалось отправить сообщение {giver_id}: {e}")

    await call.message.answer("🎉 Тайный Санта запущен! Участники получили информацию в личные сообщения.")
    await call.answer()

@dp.callback_query(F.data == "reset")
async def reset_game(call: CallbackQuery):
    chat_id = call.message.chat.id
    cur.execute("DELETE FROM participants WHERE chat_id=?", (chat_id,))
    db.commit()
    await call.message.answer("♻️ Игра очищена")
    await call.answer()

@dp.callback_query(F.data == "send_link")
async def send_link(call: CallbackQuery):
    chat_id = call.message.chat.id
    link = f"https://t.me/{BOT_USERNAME}?start=join_{chat_id}"
    await bot.send_message(chat_id, f"🎁 Участники! Регистрируйтесь по ссылке:\n{link}")
    await call.answer("Ссылка отправлена")

# ===== ВЫЙТИ =====
@dp.callback_query(F.data == "leave")
async def leave_game(call: CallbackQuery):
    user = call.from_user
    chat_id = call.message.chat.id
    cur.execute("DELETE FROM participants WHERE chat_id=? AND user_id=?", (chat_id, user.id))
    db.commit()
    await call.answer("🚪 Вы вышли из игры")

# ===== ЗАПУСК =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
