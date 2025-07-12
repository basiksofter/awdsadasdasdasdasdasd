import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import random
import string

API_TOKEN = '8080629127:AAEps4ODJ1nxozBqMsTnBtAN-D_VKj3HD4g'
ALLOWED_ADMINS = [7996175215]  # Замени на свой Telegram user_id

JSONBIN_API_KEY = '$2a$10$3PXvAuYMF.OZV8QAoLQSuee7HfVsaKbnl.uz0/LivcP4J//maoqfK'
JSONBIN_BIN_ID = '6871807a005f266d06b3acea'
JSONBIN_URL = f'https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}'
HEADERS = {
    'X-Master-Key': JSONBIN_API_KEY,
    'Content-Type': 'application/json'
}

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# FSM-like переменные для сброса пароля и активации
waiting_for_password = {}
waiting_for_new_password = {}
pending_nick = {}
pending_key = {}

# --- Работа с пользователями и ключами ---
def get_full_data():
    try:
        response = requests.get(JSONBIN_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()['record']
        else:
            print("Ошибка JSONBin:", response.text)
            return {"users": [], "activation_keys": []}
    except Exception as e:
        print("Ошибка при запросе к JSONBin:", e)
        return {"users": [], "activation_keys": []}

def save_full_data(data):
    try:
        response = requests.put(JSONBIN_URL, headers=HEADERS, json=data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print("Ошибка при сохранении в JSONBin:", e)
        return False

def get_users():
    return get_full_data().get('users', [])

def save_users(users):
    data = get_full_data()
    data['users'] = users
    save_full_data(data)

def get_activation_keys():
    try:
        response = requests.get(JSONBIN_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()['record'].get('activation_keys', [])
        else:
            return []
    except Exception:
        return []

def save_activation_keys(keys):
    # Загрузи весь объект, замени activation_keys, сохрани обратно
    try:
        response = requests.get(JSONBIN_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            data = response.json()['record']
            data['activation_keys'] = keys
            requests.put(JSONBIN_URL, headers=HEADERS, json=data, timeout=5)
    except Exception:
        pass

def is_admin(user_id):
    return user_id in ALLOWED_ADMINS

# --- Команды ---
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if is_admin(message.from_user.id):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Список пользователей", callback_data="user_list"))
        kb.add(InlineKeyboardButton("Создать ключ", callback_data="create_key"))
        await message.answer("Админ-панель", reply_markup=kb)
    else:
        await message.answer("Для активации ключа введите свой никнейм:")
        pending_nick[message.from_user.id] = True

@dp.message_handler(commands=['addkey'])
async def add_key(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) != 3 or args[2] not in ['user', 'beta', 'alpha']:
        await message.answer("Использование: /addkey <ключ> <роль: user|beta|alpha>")
        return
    key, role = args[1], args[2]
    keys = get_activation_keys()
    keys.append({"key": key, "role": role})
    save_activation_keys(keys)
    await message.answer(f"Ключ <code>{key}</code> для роли <b>{role}</b> добавлен.", parse_mode="HTML")

# --- FSM: активация ключа ---
@dp.message_handler(lambda message: pending_nick.get(message.from_user.id))
async def process_nick(message: types.Message):
    users = get_users()
    user = next((u for u in users if u["username"].lower() == message.text.strip().lower()), None)
    if user:
        pending_key[message.from_user.id] = user["username"]
        del pending_nick[message.from_user.id]
        await message.answer("Введите ключ активации:")
    else:
        await message.answer("❌ Пользователь с таким никнеймом не найден. Попробуйте снова.")

@dp.message_handler(lambda message: pending_key.get(message.from_user.id))
async def process_key(message: types.Message):
    username = pending_key[message.from_user.id]
    keys = get_activation_keys()
    key_obj = next((k for k in keys if k["key"] == message.text.strip()), None)
    if key_obj:
        users = get_users()
        user = next((u for u in users if u["username"].lower() == username.lower()), None)
        if user:
            user["role"] = key_obj["role"]
            save_users(users)
            # Удаляем использованный ключ
            keys = [k for k in keys if k["key"] != key_obj["key"]]
            save_activation_keys(keys)
            await message.answer(f"✅ Активация прошла успешно! Ваша роль: <b>{key_obj['role'].capitalize()}</b>", parse_mode="HTML")
        else:
            await message.answer("❌ Пользователь не найден.")
        del pending_key[message.from_user.id]
    else:
        await message.answer("❌ Неверный ключ. Попробуйте снова.")

# --- Админка ---
@dp.callback_query_handler(lambda c: c.data == 'user_list')
async def show_users(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    users = get_users()
    kb = InlineKeyboardMarkup()
    for user in users:
        text = f"{user['username']} | UID: {user['uid']} | {user['role'].capitalize()}"
        kb.add(InlineKeyboardButton(text=text, callback_data=f"user_{user['uid']}"))
    await callback_query.message.edit_text("👥 <b>Список пользователей:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith('user_'))
async def user_menu(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    uid = int(callback_query.data.split('_')[1])
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    if not user:
        await callback_query.answer("Пользователь не найден", show_alert=True)
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text="🛡 Роль", callback_data=f"role_{uid}"),
        InlineKeyboardButton(text="🔄 HWID", callback_data=f"hwid_{uid}"),
        InlineKeyboardButton(text="🔑 Пароль", callback_data=f"resetpass_{uid}")
    )
    text = (
        f"👤 <b>{user['username']}</b>\n"
        f"🆔 <b>UID:</b> <code>{user['uid']}</code>\n"
        f"🛡 <b>Роль:</b> <code>{user['role'].capitalize()}</code>\n"
        f"💻 <b>HWID:</b> <code>{user['hwid'] or '—'}</code>\n"
        f"📅 <b>Создан:</b> <code>{user.get('createdAt', '—')[:10]}</code>"
    )
    await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith('role_'))
async def change_role(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    uid = int(callback_query.data.split('_')[1])
    kb = InlineKeyboardMarkup(row_width=2)
    for role, emoji in [("user", "👤"), ("beta", "🧪"), ("alpha", "🦄"), ("admin", "👑")]:
        kb.add(InlineKeyboardButton(text=f"{emoji} {role.capitalize()}", callback_data=f"setrole_{uid}_{role}"))
    await callback_query.message.edit_text("Выберите новую роль:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('setrole_'))
async def set_role(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    _, uid, role = callback_query.data.split('_')
    uid = int(uid)
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    if user:
        user["role"] = role
        save_users(users)
        await callback_query.message.edit_text(f"✅ Роль пользователя обновлена на <b>{role.capitalize()}</b>", parse_mode="HTML")
    else:
        await callback_query.answer("Пользователь не найден", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('hwid_'))
async def reset_hwid(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    uid = int(callback_query.data.split('_')[1])
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    if user:
        user["hwid"] = ""
        save_users(users)
        await callback_query.message.edit_text("✅ HWID сброшен.")
    else:
        await callback_query.answer("Пользователь не найден", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('resetpass_'))
async def ask_current_password(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    uid = int(callback_query.data.split('_')[1])
    waiting_for_password[callback_query.from_user.id] = uid
    await callback_query.message.edit_text("Введите текущий пароль пользователя:")

@dp.message_handler(lambda message: message.from_user.id in waiting_for_password)
async def check_current_password(message: types.Message):
    uid = waiting_for_password[message.from_user.id]
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    if user and message.text == user["password"]:
        waiting_for_new_password[message.from_user.id] = uid
        del waiting_for_password[message.from_user.id]
        await message.answer("Введите новый пароль:")
    else:
        await message.answer("❌ Неверный пароль. Попробуйте снова.")

@dp.message_handler(lambda message: message.from_user.id in waiting_for_new_password)
async def set_new_password(message: types.Message):
    uid = waiting_for_new_password[message.from_user.id]
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    if user:
        user["password"] = message.text
        save_users(users)
        await message.answer("✅ Пароль успешно изменён.")
    else:
        await message.answer("Ошибка пользователя.")
    del waiting_for_new_password[message.from_user.id]

@dp.callback_query_handler(lambda c: c.data == 'create_key')
async def create_key_menu(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton(text="👤 User", callback_data="genkey_user"),
        InlineKeyboardButton(text="🧪 Beta", callback_data="genkey_beta"),
        InlineKeyboardButton(text="🦄 Alpha", callback_data="genkey_alpha")
    )
    await callback_query.message.edit_text("Выберите роль для нового ключа:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('genkey_'))
async def generate_and_send_key(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Доступ запрещён.", show_alert=True)
        return
    role = callback_query.data.split('_')[1]
    key = generate_key()
    keys = get_activation_keys()
    keys.append({"key": key, "role": role})
    save_activation_keys(keys)
    await callback_query.message.edit_text(
        f"✅ Ключ создан!\n\n<code>{key}</code>\nРоль: <b>{role.capitalize()}</b>",
        parse_mode="HTML"
    )

def generate_key(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)