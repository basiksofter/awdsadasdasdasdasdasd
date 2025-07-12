import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import random
import string
from typing import Dict, List, Optional, TypedDict

API_TOKEN = '8080629127:AAEps4ODJ1nxozBqMsTnBtAN-D_VKj3HD4g'
ALLOWED_ADMINS = [7996175215]  # Замени на свой Telegram user_id

JSONBIN_API_KEY = '$2a$10$3PXvAuYMF.OZV8QAoLQSuee7HfVsaKbnl.uz0/LivcP4J//maoqfK'
JSONBIN_BIN_ID = '6871807a005f266d06b3acea'
JSONBIN_URL = f'https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}'
HEADERS: Dict[str, str] = {
    'X-Master-Key': JSONBIN_API_KEY,
    'Content-Type': 'application/json'
}

class User(TypedDict):
    username: str
    uid: int
    role: str
    hwid: str
    password: str
    createdAt: str

class ActivationKey(TypedDict):
    key: str
    role: str

bot: Bot = Bot(token=API_TOKEN)
dp: Dispatcher = Dispatcher(bot)

# Состояния FSM
waiting_for_password: Dict[int, int] = {}
waiting_for_new_password: Dict[int, int] = {}
pending_nick: Dict[int, bool] = {}
pending_key: Dict[int, str] = {}

def get_full_data() -> Dict:
    try:
        response = requests.get(JSONBIN_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()['record']
        print(f"Ошибка JSONBin: {response.text}")
        return {"users": [], "activation_keys": []}
    except Exception as e:
        print(f"Ошибка запроса к JSONBin: {e}")
        return {"users": [], "activation_keys": []}

def save_full_data(data: Dict) -> bool:
    try:
        response = requests.put(JSONBIN_URL, headers=HEADERS, json=data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка сохранения в JSONBin: {e}")
        return False

def get_users() -> List[User]:
    return get_full_data().get('users', [])

def save_users(users: List[User]) -> bool:
    data = get_full_data()
    data['users'] = users
    return save_full_data(data)

def get_activation_keys() -> List[ActivationKey]:
    try:
        response = requests.get(JSONBIN_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()['record'].get('activation_keys', [])
        return []
    except Exception as e:
        print(f"Ошибка получения ключей: {e}")
        return []

def save_activation_keys(keys: List[ActivationKey]) -> None:
    try:
        response = requests.get(JSONBIN_URL, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            data = response.json()['record']
            data['activation_keys'] = keys
            requests.put(JSONBIN_URL, headers=HEADERS, json=data, timeout=5)
    except Exception as e:
        print(f"Ошибка сохранения ключей: {e}")

def is_admin(user_id: int) -> bool:
    return user_id in ALLOWED_ADMINS

def generate_key(length: int = 12) -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message) -> None:
    if is_admin(message.from_user.id):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📋 Список пользователей", callback_data="user_list"))
        kb.add(InlineKeyboardButton("🔑 Создать ключ", callback_data="create_key"))
        await message.answer("👨‍💻 Панель администратора", reply_markup=kb)
    else:
        await message.answer("Для активации ключа введите ваш никнейм:")
        pending_nick[message.from_user.id] = True

@dp.message_handler(commands=['addkey'])
async def add_key(message: types.Message) -> None:
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) != 3 or args[2] not in {'user', 'beta', 'alpha'}:
        await message.answer("Использование: /addkey <ключ> <роль: user|beta|alpha>")
        return
    
    key, role = args[1], args[2]
    keys = get_activation_keys()
    keys.append({"key": key, "role": role})
    save_activation_keys(keys)
    await message.answer(f"✅ Ключ <code>{key}</code> для роли <b>{role}</b> успешно добавлен.", parse_mode="HTML")

@dp.message_handler(lambda message: pending_nick.get(message.from_user.id))
async def process_nick(message: types.Message) -> None:
    users = get_users()
    username = message.text.strip().lower()
    user = next((u for u in users if u["username"].lower() == username), None)
    
    if user:
        pending_key[message.from_user.id] = user["username"]
        del pending_nick[message.from_user.id]
        await message.answer("Теперь введите ваш ключ активации:")
    else:
        await message.answer("❌ Пользователь с таким никнеймом не найден. Пожалуйста, попробуйте еще раз.")

@dp.message_handler(lambda message: pending_key.get(message.from_user.id))
async def process_key(message: types.Message) -> None:
    username = pending_key[message.from_user.id]
    keys = get_activation_keys()
    input_key = message.text.strip()
    key_obj = next((k for k in keys if k["key"] == input_key), None)
    
    if not key_obj:
        await message.answer("❌ Неверный ключ активации. Пожалуйста, попробуйте еще раз.")
        return
    
    users = get_users()
    user = next((u for u in users if u["username"].lower() == username.lower()), None)
    
    if user:
        user["role"] = key_obj["role"]
        save_users(users)
        keys = [k for k in keys if k["key"] != key_obj["key"]]
        save_activation_keys(keys)
        await message.answer(
            f"✅ Активация прошла успешно! Ваша новая роль: <b>{key_obj['role'].capitalize()}</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка: пользователь не найден.")
    
    del pending_key[message.from_user.id]

@dp.callback_query_handler(lambda c: c.data == 'user_list')
async def show_users(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    users = get_users()
    kb = InlineKeyboardMarkup()
    
    for user in users:
        text = f"{user['username']} | ID: {user['uid']} | {user['role'].capitalize()}"
        kb.add(InlineKeyboardButton(text=text, callback_data=f"user_{user['uid']}"))
    
    await callback_query.message.edit_text("👥 <b>Список пользователей:</b>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith('user_'))
async def user_menu(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    try:
        uid = int(callback_query.data.split('_')[1])
    except ValueError:
        await callback_query.answer("❌ Неверный ID пользователя", show_alert=True)
        return
    
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    
    if not user:
        await callback_query.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text="🛡 Изменить роль", callback_data=f"role_{uid}"),
        InlineKeyboardButton(text="🔄 Сбросить HWID", callback_data=f"hwid_{uid}"),
        InlineKeyboardButton(text="🔑 Изменить пароль", callback_data=f"resetpass_{uid}")
    )
    
    text = (
        f"👤 <b>Пользователь:</b> {user['username']}\n"
        f"🆔 <b>ID:</b> <code>{user['uid']}</code>\n"
        f"🛡 <b>Роль:</b> <code>{user['role'].capitalize()}</code>\n"
        f"💻 <b>HWID:</b> <code>{user['hwid'] or 'не установлен'}</code>\n"
        f"📅 <b>Дата регистрации:</b> <code>{user.get('createdAt', 'неизвестно')[:10]}</code>"
    )
    
    await callback_query.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith('role_'))
async def change_role(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    uid = int(callback_query.data.split('_')[1])
    kb = InlineKeyboardMarkup(row_width=2)
    for role, emoji in [("user", "👤 Обычный"), ("beta", "🧪 Тестер"), ("alpha", "🦄 Альфа"), ("admin", "👑 Админ")]:
        kb.add(InlineKeyboardButton(text=f"{emoji}", callback_data=f"setrole_{uid}_{role}"))
    await callback_query.message.edit_text("Выберите новую роль для пользователя:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('setrole_'))
async def set_role(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    _, uid, role = callback_query.data.split('_')
    uid = int(uid)
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    
    if user:
        user["role"] = role
        save_users(users)
        await callback_query.message.edit_text(f"✅ Роль пользователя успешно изменена на <b>{role.capitalize()}</b>", parse_mode="HTML")
    else:
        await callback_query.answer("❌ Пользователь не найден", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('hwid_'))
async def reset_hwid(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    uid = int(callback_query.data.split('_')[1])
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    
    if user:
        user["hwid"] = ""
        save_users(users)
        await callback_query.message.edit_text("✅ HWID пользователя успешно сброшен.")
    else:
        await callback_query.answer("❌ Пользователь не найден", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith('resetpass_'))
async def ask_current_password(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    uid = int(callback_query.data.split('_')[1])
    waiting_for_password[callback_query.from_user.id] = uid
    await callback_query.message.edit_text("Введите текущий пароль пользователя:")

@dp.message_handler(lambda message: message.from_user.id in waiting_for_password)
async def check_current_password(message: types.Message) -> None:
    uid = waiting_for_password[message.from_user.id]
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    
    if user and message.text == user["password"]:
        waiting_for_new_password[message.from_user.id] = uid
        del waiting_for_password[message.from_user.id]
        await message.answer("Введите новый пароль для пользователя:")
    else:
        await message.answer("❌ Неверный пароль. Пожалуйста, попробуйте еще раз.")

@dp.message_handler(lambda message: message.from_user.id in waiting_for_new_password)
async def set_new_password(message: types.Message) -> None:
    uid = waiting_for_new_password[message.from_user.id]
    users = get_users()
    user = next((u for u in users if u["uid"] == uid), None)
    
    if user:
        user["password"] = message.text
        save_users(users)
        await message.answer("✅ Пароль пользователя успешно изменен.")
    else:
        await message.answer("❌ Ошибка: пользователь не найден")
    
    del waiting_for_new_password[message.from_user.id]

@dp.callback_query_handler(lambda c: c.data == 'create_key')
async def create_key_menu(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton(text="👤 Обычный", callback_data="genkey_user"),
        InlineKeyboardButton(text="🧪 Тестер", callback_data="genkey_beta"),
        InlineKeyboardButton(text="🦄 Альфа", callback_data="genkey_alpha")
    )
    await callback_query.message.edit_text("Выберите тип ключа для создания:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('genkey_'))
async def generate_and_send_key(callback_query: types.CallbackQuery) -> None:
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    role = callback_query.data.split('_')[1]
    key = generate_key()
    keys = get_activation_keys()
    keys.append({"key": key, "role": role})
    save_activation_keys(keys)
    
    role_names = {
        'user': 'Обычный',
        'beta': 'Тестер',
        'alpha': 'Альфа'
    }
    
    await callback_query.message.edit_text(
        f"✅ Ключ успешно создан!\n\n"
        f"🔑 <b>Ключ:</b> <code>{key}</code>\n"
        f"👤 <b>Тип:</b> {role_names.get(role, role.capitalize())}",
        parse_mode="HTML"
    )

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
