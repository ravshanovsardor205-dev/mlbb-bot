"""
MLBB Duo Finder Bot — PRODUCTION VERSION
Railway-ga optimallashtirilgan
pip install aiogram aiosqlite python-dotenv
"""
import asyncio
import logging
import json
import os
from datetime import datetime
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
import aiosqlite

# ─────────────────────────────────────────────
# .env fayldan TOKEN o'qish
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "8830561217:AAGfXR1HhpZMgvmeJW7DUaF2xdiby1j845c")
DB    = os.getenv("DATABASE", "mlbb.db")
# ─────────────────────────────────────────────

bot     = Bot(token=TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
RANKS = ["Warrior", "Elite", "Master", "Grandmaster",
         "Epic", "Legend", "Mythic", "Mythical Glory"]

RANK_EMOJI = {
    "Warrior":"⚔️","Elite":"🛡️","Master":"🔮","Grandmaster":"💎",
    "Epic":"🌟","Legend":"👑","Mythic":"🔱","Mythical Glory":"🏆",
}

ROLES = ["Roamer", "Gold Lane", "Exp Lane", "Mid Lane", "Jungler"]

ROLE_EMOJI = {
    "Roamer":"🗺️","Gold Lane":"💰","Exp Lane":"⚡",
    "Mid Lane":"🎯","Jungler":"🌲",
}

# ─────────────────────────────────────────────
#  FSM
# ─────────────────────────────────────────────
class Setup(StatesGroup):
    rank = State()
    roles = State()
    finding_rank = State()
    finding_roles = State()

class Messaging(StatesGroup):
    typing_message = State()

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
async def init_db():
    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id              INTEGER PRIMARY KEY,
                    username             TEXT DEFAULT '',
                    full_name            TEXT DEFAULT '',
                    rank                 TEXT DEFAULT 'Unranked',
                    roles                TEXT DEFAULT '[]',
                    looking_for_rank     TEXT DEFAULT 'Unranked',
                    looking_for_roles    TEXT DEFAULT '[]'
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    msg_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_id   INTEGER NOT NULL,
                    to_id     INTEGER NOT NULL,
                    text      TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_read   INTEGER DEFAULT 0
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    announce_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id    INTEGER NOT NULL,
                    rank       TEXT NOT NULL,
                    roles      TEXT NOT NULL,
                    timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

async def db_get(user_id: int):
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT user_id, username, full_name, rank, roles, looking_for_rank, looking_for_roles "
                "FROM users WHERE user_id=?",
                (user_id,)
            )
            return await cur.fetchone()
    except Exception as e:
        logger.error(f"❌ db_get error: {e}")
        return None

async def db_save(user_id: int, username: str, full_name: str,
                  rank: str = None, roles: list = None,
                  looking_for_rank: str = None, looking_for_roles: list = None):
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT rank, roles, looking_for_rank, looking_for_roles FROM users WHERE user_id=?", 
                (user_id,)
            )
            row = await cur.fetchone()
            
            new_rank = rank if rank and rank != "Unranked" else (row[0] if row else "Unranked")
            new_roles = roles if roles else (json.loads(row[1]) if row and row[1] else [])
            new_looking_rank = looking_for_rank if looking_for_rank and looking_for_rank != "Unranked" else (row[2] if row else "Unranked")
            new_looking_roles = looking_for_roles if looking_for_roles else (json.loads(row[3]) if row and row[3] else [])
            
            roles_json = json.dumps(new_roles) if isinstance(new_roles, list) else new_roles
            looking_roles_json = json.dumps(new_looking_roles) if isinstance(new_looking_roles, list) else new_looking_roles
            
            if row is None:
                await db.execute(
                    "INSERT INTO users (user_id, username, full_name, rank, roles, looking_for_rank, looking_for_roles) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (user_id, username, full_name, new_rank, roles_json, new_looking_rank, looking_roles_json)
                )
            else:
                await db.execute(
                    "UPDATE users SET username=?, full_name=?, rank=?, roles=?, looking_for_rank=?, looking_for_roles=? "
                    "WHERE user_id=?",
                    (username, full_name, new_rank, roles_json, new_looking_rank, looking_roles_json, user_id)
                )
            
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"❌ db_save error: {e}")
        return False

async def save_message(from_id: int, to_id: int, text: str):
    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT INTO messages (from_id, to_id, text) VALUES (?,?,?)",
                (from_id, to_id, text)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"❌ save_message error: {e}")
        return False

async def get_messages(from_id: int, to_id: int):
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT msg_id, from_id, text, timestamp FROM messages "
                "WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) "
                "ORDER BY timestamp ASC",
                (from_id, to_id, to_id, from_id)
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"❌ get_messages error: {e}")
        return []

async def get_contacts(user_id: int):
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT DISTINCT CASE WHEN from_id=? THEN to_id ELSE from_id END as contact_id "
                "FROM messages WHERE from_id=? OR to_id=? ORDER BY timestamp DESC",
                (user_id, user_id, user_id)
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"❌ get_contacts error: {e}")
        return []

async def add_announcement(user_id: int, rank: str, roles: list):
    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM announcements WHERE user_id=?", (user_id,))
            await db.execute(
                "INSERT INTO announcements (user_id, rank, roles) VALUES (?,?,?)",
                (user_id, rank, json.dumps(roles))
            )
            await db.commit()
            logger.info(f"✅ E'lon qo'shildi: [{user_id}] {rank} - {roles}")
            return True
    except Exception as e:
        logger.error(f"❌ add_announcement error: {e}")
        return False

async def get_user_announcement(user_id: int):
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute(
                "SELECT announce_id, user_id, rank, roles, timestamp FROM announcements WHERE user_id=?",
                (user_id,)
            )
            result = await cur.fetchone()
            logger.info(f"🔍 E'lon qidirish [{user_id}]: {result}")
            return result
    except Exception as e:
        logger.error(f"❌ get_user_announcement error: {e}")
        return None

async def delete_announcement(user_id: int):
    try:
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM announcements WHERE user_id=?", (user_id,))
            await db.commit()
            logger.info(f"❌ E'lon o'chirildi: [{user_id}]")
            return True
    except Exception as e:
        logger.error(f"❌ delete_announcement error: {e}")
        return False

async def get_announcements_by_rank_and_roles(rank: str, roles: list):
    """E'lon bergan foydalanuvchilarni rank va rollari bo'yicha qidirish"""
    try:
        async with aiosqlite.connect(DB) as db:
            idx = RANKS.index(rank)
            nearby_ranks = [RANKS[i] for i in range(max(0, idx-1), min(len(RANKS), idx+2))]
            
            rank_placeholders = ",".join("?" * len(nearby_ranks))
            
            cur = await db.execute(
                f"SELECT user_id, rank, roles FROM announcements "
                f"WHERE rank IN ({rank_placeholders}) "
                f"ORDER BY timestamp DESC",
                nearby_ranks
            )
            rows = await cur.fetchall()
            
            logger.info(f"📊 Topilgan e'lonlar: {len(rows)} ta (Rank: {nearby_ranks})")
            
            matched = []
            for user_id, ann_rank, roles_str in rows:
                try:
                    ann_roles = json.loads(roles_str) if roles_str else []
                except:
                    ann_roles = []
                
                if any(role in ann_roles for role in roles):
                    user_data = await db_get(user_id)
                    if user_data:
                        matched.append((user_id, user_data[1], user_data[2], ann_rank, ann_roles))
                        logger.info(f"✅ Sherik topildi: {user_id} - {ann_rank} - {ann_roles}")
            
            logger.info(f"🎯 Ishtirok etgan sheriklar: {len(matched)} ta")
            return matched
    except Exception as e:
        logger.error(f"❌ get_announcements_by_rank_and_roles error: {e}")
        return []

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def is_profile_complete(rank: str, roles_str) -> bool:
    try:
        if rank in (None, "Unranked", ""):
            return False
        
        roles_list = []
        if isinstance(roles_str, str):
            roles_list = json.loads(roles_str) if roles_str and roles_str != "[]" else []
        elif isinstance(roles_str, list):
            roles_list = roles_str
        
        return len(roles_list) > 0
    except Exception as e:
        logger.error(f"❌ is_profile_complete error: {e}")
        return False

def re(r): 
    return RANK_EMOJI.get(r, "🏅")

def ro(r): 
    return ROLE_EMOJI.get(r, "🎮")

def format_roles(roles_str) -> str:
    try:
        if isinstance(roles_str, str):
            roles_list = json.loads(roles_str) if roles_str else []
        else:
            roles_list = roles_str if roles_str else []
        
        if not roles_list:
            return "❌ Tanlanmagan"
        return "  ".join([f"{ro(r)} {r}" for r in roles_list])
    except Exception as e:
        logger.error(f"❌ format_roles error: {e}")
        return "❌ Xato"

# ─────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Profil"),     KeyboardButton(text="🔍 Sherik topish")],
            [KeyboardButton(text="📢 E'lon berish"),  KeyboardButton(text="💬 Xabarlar")],
            [KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Buyruq tanlang..."
    )

def rank_kb():
    rows, row = [], []
    for r in RANKS:
        row.append(InlineKeyboardButton(text=f"{re(r)} {r}", callback_data=f"rank:{r}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def roles_kb(prefix: str = "role"):
    rows = []
    for i, r in enumerate(ROLES):
        if i % 2 == 0:
            row = []
        row.append(InlineKeyboardButton(
            text=f"☐ {ro(r)} {r}", 
            callback_data=f"{prefix}:{r}"
        ))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data=f"{prefix}:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Rank", callback_data="edit_rank"),
            InlineKeyboardButton(text="✏️ Rollar",  callback_data="edit_roles"),
        ],
        [
            InlineKeyboardButton(text="🔍 Sherik topish", callback_data="find_duo"),
            InlineKeyboardButton(text="📢 E'lon berish",     callback_data="announce_duo"),
        ],
    ])

def announce_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, e'lon ber", callback_data="confirm_announce"),
        InlineKeyboardButton(text="❌ Bekor",         callback_data="cancel"),
    ]])

# ─────────────────────────────────────────────
#  PROFILE DISPLAY
# ─────────────────────────────────────────────
async def send_profile(target: types.Message, user_id: int):
    u = await db_get(user_id)
    
    if not u:
        await target.answer(
            "❌ Profil topilmadi.\n/start bilan boshlang.",
            reply_markup=main_kb()
        )
        return
    
    _, uname, fname, rank, roles, looking_for_rank, looking_for_roles = u
    is_complete = is_profile_complete(rank, roles)
    login = f"@{uname}" if uname else fname or "—"
    
    roles_text = format_roles(roles)
    looking_text = format_roles(looking_for_roles)
    
    announcement = await get_user_announcement(user_id)
    announce_status = "✅ E'lon berilgan" if announcement else "❌ E'lon berilmagan"
    
    msg = (
        f"👤 <b>PROFILINGIZ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 Ism:   {fname or '—'}\n"
        f"🔹 Login: {login}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>🎮 SIZNING MA'LUMOTLARINGIZ</b>\n"
        f"{re(rank)} Rank: <b>{rank}</b>\n"
        f"Rollar: {roles_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📢 E'LON</b>\n"
        f"{announce_status}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{'✅ <b>To\'liq</b>' if is_complete else '⚠️ <b>To\'liq emas</b>'}"
    )
    
    kb = profile_kb()
    
    if announcement:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Rank", callback_data="edit_rank"),
                InlineKeyboardButton(text="✏️ Rollar",  callback_data="edit_roles"),
            ],
            [
                InlineKeyboardButton(text="🔍 Sherik topish", callback_data="find_duo"),
                InlineKeyboardButton(text="📢 E'lon berish",     callback_data="announce_duo"),
            ],
            [
                InlineKeyboardButton(text="❌ E'lonni o'chirish", callback_data="delete_announce"),
            ],
        ])
    
    await target.answer(msg, parse_mode="HTML", reply_markup=kb)

# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    uname = message.from_user.username or ""
    fname = message.from_user.full_name or ""
    user_id = message.from_user.id
    
    await db_save(user_id, uname, fname)
    
    user = await db_get(user_id)
    is_complete = user and is_profile_complete(user[3], user[4])
    
    name = fname or uname or "Foydalanuvchi"
    
    await message.answer(
        f"👋 Salom, <b>{name}</b>!\n\n"
        "🔥 <b>MLBB Duo Finder</b> botga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan foydalaning 👇",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
    
    if not is_complete:
        await message.answer(
            "📋 <b>Profilingizni to'ldiring!</b>\n\n"
            "1️⃣ <b>Rankingizni tanlang:</b>",
            parse_mode="HTML",
            reply_markup=rank_kb()
        )
        await state.set_state(Setup.rank)

@dp.message(Command("profile"))
@dp.message(F.text == "👤 Profil")
async def cmd_profile(message: types.Message, state: FSMContext):
    await state.clear()
    await send_profile(message, message.from_user.id)

@dp.callback_query(F.data == "edit_rank")
async def cb_edit_rank(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Setup.rank)
    await call.message.answer(
        "🏆 <b>Rankingizni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=rank_kb()
    )
    await call.answer()

@dp.callback_query(StateFilter(Setup.rank), F.data.startswith("rank:"))
async def cb_set_rank(call: types.CallbackQuery, state: FSMContext):
    rank = call.data.split(":", 1)[1]
    
    if rank not in RANKS:
        await call.answer("❌ Noto'g'ri!", show_alert=True)
        return
    
    await state.update_data(setup_rank=rank)
    
    await call.message.edit_text(
        f"✅ Rank tanlandi: <b>{re(rank)} {rank}</b>\n\n"
        f"2️⃣ <b>Rollarni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=roles_kb("setup_role")
    )
    await state.set_state(Setup.roles)
    await call.answer()

@dp.callback_query(StateFilter(Setup.roles), F.data.startswith("setup_role:"))
async def cb_toggle_role(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":", 1)[1]
    
    if role == "done":
        data = await state.get_data()
        selected_roles = data.get("setup_roles", [])
        setup_rank = data.get("setup_rank", "Unranked")
        
        if not selected_roles:
            await call.answer("❌ Kamita 1ta rol tanlang!", show_alert=True)
            return
        
        uname = call.from_user.username or ""
        fname = call.from_user.full_name or ""
        success = await db_save(
            call.from_user.id, 
            uname, 
            fname,
            rank=setup_rank,
            roles=selected_roles
        )
        
        if not success:
            await call.answer("❌ Saqlash xatosi!", show_alert=True)
            return
        
        await call.message.edit_text(
            f"✅ <b>Saqlandi!</b>\n\n"
            f"{re(setup_rank)} Rank: <b>{setup_rank}</b>\n"
            f"Rollar: {format_roles(selected_roles)}",
            parse_mode="HTML"
        )
        
        await asyncio.sleep(0.5)
        await state.clear()
        await send_profile(call.message, call.from_user.id)
        await call.answer()
        return
    
    if role not in ROLES:
        await call.answer("❌ Noto'g'ri!", show_alert=True)
        return
    
    data = await state.get_data()
    selected_roles = data.get("setup_roles", [])
    
    if role in selected_roles:
        selected_roles.remove(role)
    else:
        selected_roles.append(role)
    
    await state.update_data(setup_roles=selected_roles)
    
    rows = []
    for i, r in enumerate(ROLES):
        if i % 2 == 0:
            row = []
        checked = "☑️" if r in selected_roles else "☐"
        row.append(InlineKeyboardButton(
            text=f"{checked} {ro(r)} {r}", 
            callback_data=f"setup_role:{r}"
        ))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="setup_role:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "edit_roles")
async def cb_edit_roles(call: types.CallbackQuery, state: FSMContext):
    u = await db_get(call.from_user.id)
    if not u:
        await call.answer("❌ Profil topilmadi!", show_alert=True)
        return
    
    current_roles = json.loads(u[4]) if u[4] else []
    await state.update_data(setup_roles=current_roles, setup_rank=u[3])
    await state.set_state(Setup.roles)
    
    await call.message.answer(
        "🎮 <b>Rollarni o'zgartiring:</b>",
        parse_mode="HTML",
        reply_markup=roles_kb("setup_role")
    )
    await call.answer()

@dp.callback_query(F.data == "find_duo")
@dp.message(F.text == "🔍 Sherik topish")
async def cmd_find(message_or_call, state: FSMContext):
    await state.clear()
    
    if isinstance(message_or_call, types.CallbackQuery):
        user_id = message_or_call.from_user.id
        target = message_or_call.message
        await message_or_call.answer()
    else:
        user_id = message_or_call.from_user.id
        target = message_or_call
    
    u = await db_get(user_id)
    
    if not u:
        await target.answer(
            "❌ Profil topilmadi. /start bilan boshlang.",
            reply_markup=main_kb()
        )
        return
    
    is_complete = is_profile_complete(u[3], u[4])
    
    if not is_complete:
        await target.answer(
            "⚠️ <b>XATO!</b> Profilingiz to'liq emas!\n\n"
            "👤 Profil tugmasini bosib:\n"
            "✅ Rankni tanlang\n"
            "✅ Rollarni tanlang\n\n"
            "Keyin yana urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=main_kb()
        )
        return
    
    await target.answer(
        "🔍 <b>SHERIK QIDIRISH</b>\n\n"
        "1️⃣ <b>Kerakli rankni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=rank_kb()
    )
    await state.set_state(Setup.finding_rank)

@dp.callback_query(StateFilter(Setup.finding_rank), F.data.startswith("rank:"))
async def cb_finding_rank(call: types.CallbackQuery, state: FSMContext):
    rank = call.data.split(":", 1)[1]
    
    if rank not in RANKS:
        await call.answer("❌ Noto'g'ri!", show_alert=True)
        return
    
    await state.update_data(finding_rank=rank)
    
    await call.message.edit_text(
        f"✅ Rank tanlandi: <b>{re(rank)} {rank}</b>\n\n"
        f"2️⃣ <b>Kerakli rollarni tanlang:</b>",
        parse_mode="HTML",
        reply_markup=roles_kb("finding_role")
    )
    await state.set_state(Setup.finding_roles)
    await call.answer()

@dp.callback_query(StateFilter(Setup.finding_roles), F.data.startswith("finding_role:"))
async def cb_toggle_finding_role(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":", 1)[1]
    
    if role == "done":
        data = await state.get_data()
        finding_roles = data.get("finding_roles", [])
        finding_rank = data.get("finding_rank", "Unranked")
        
        if not finding_roles:
            await call.answer("❌ Kamita 1ta rol tanlang!", show_alert=True)
            return
        
        matched = await get_announcements_by_rank_and_roles(finding_rank, finding_roles)
        
        if not matched:
            await call.message.edit_text(
                f"😔 <b>{finding_rank}</b> darajasida sherik topilmadi.\n\n"
                f"💡 Foydalanuvchilar e'lon berishini kutib uring!",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        result_text = (
            f"✅ <b>TOPILGAN SHERIKLAR</b>\n\n"
            f"📊 Rank: <b>{finding_rank}</b> ±1\n"
            f"🎮 Rollar: {format_roles(finding_roles)}\n\n"
            f"🔍 Jami: <b>{len(matched)}</b> ta\n\n"
            f"💬 Istaganingizga tanlab xabar yuboring!"
        )
        
        await call.message.edit_text(result_text, parse_mode="HTML")
        
        await bot.send_message(
            call.from_user.id,
            f"✅ <b>TOPILGAN {len(matched)} TA SHERIK</b>\n\n"
            f"📊 Rank: <b>{finding_rank}</b> ±1\n"
            f"🎮 Rollar: {format_roles(finding_roles)}\n\n"
            f"Quyidagi sheriklar sizga yozishlari mumkin 👇",
            parse_mode="HTML"
        )
        
        for idx, (uid, uname, fname, urank, user_roles) in enumerate(matched, 1):
            login = f"@{uname}" if uname else fname or "NoName"
            user_display = fname or login
            
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="💬 Xabar yuborish", 
                    callback_data=f"send_msg:{uid}"
                )
            ]])
            
            text = (
                f"<b>#{idx}. {user_display}</b>\n"
                f"🔑 {login}\n\n"
                f"{re(urank)} <b>Rank:</b> {urank}\n"
                f"🎮 <b>Rollar:</b> {format_roles(user_roles)}"
            )
            
            await bot.send_message(
                call.from_user.id,
                text,
                parse_mode="HTML",
                reply_markup=kb
            )
        
        await state.clear()
        return
    
    if role not in ROLES:
        await call.answer("❌ Noto'g'ri!", show_alert=True)
        return
    
    data = await state.get_data()
    finding_roles = data.get("finding_roles", [])
    
    if role in finding_roles:
        finding_roles.remove(role)
    else:
        finding_roles.append(role)
    
    await state.update_data(finding_roles=finding_roles)
    
    rows = []
    for i, r in enumerate(ROLES):
        if i % 2 == 0:
            row = []
        checked = "☑️" if r in finding_roles else "☐"
        row.append(InlineKeyboardButton(
            text=f"{checked} {ro(r)} {r}", 
            callback_data=f"finding_role:{r}"
        ))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    
    rows.append([InlineKeyboardButton(text="✅ Qidirni boshlash", callback_data="finding_role:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    
    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data.startswith("send_msg:"))
async def cb_send_msg(call: types.CallbackQuery, state: FSMContext):
    to_id_str = call.data.split(":")[1]
    
    try:
        to_id = int(to_id_str)
    except:
        await call.answer("❌ Xato!", show_alert=True)
        return
    
    to_user = await db_get(to_id)
    
    if not to_user:
        await call.answer("❌ Foydalanuvchi topilmadi!", show_alert=True)
        return
    
    to_name = to_user[2] or f"@{to_user[1]}" or "Foydalanuvchi"
    to_rank = to_user[3]
    to_roles = to_user[4]
    
    await state.update_data(
        msg_to_id=to_id, 
        msg_to_name=to_name,
        msg_to_rank=to_rank,
        msg_to_roles=to_roles
    )
    await state.set_state(Messaging.typing_message)
    
    await call.message.answer(
        f"💬 <b>{to_name}</b> ga xabar yozing:\n\n"
        f"{re(to_rank)} {to_rank}\n"
        f"🎮 {format_roles(to_roles)}\n\n"
        f"Yoki /cancel",
        parse_mode="HTML"
    )
    await call.answer()

@dp.message(StateFilter(Messaging.typing_message))
async def msg_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    to_id = data.get("msg_to_id")
    to_name = data.get("msg_to_name")
    
    if not to_id:
        await message.answer("❌ Xato.")
        await state.clear()
        return
    
    success = await save_message(message.from_user.id, to_id, message.text)
    
    if not success:
        await message.answer("❌ Yuborilmadi!")
        return
    
    await message.answer(
        f"✅ <b>{to_name}</b> ga yuborildi!",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
    
    from_name = message.from_user.full_name or f"@{message.from_user.username}" or "Foydalanuvchi"
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Javob", callback_data=f"send_msg:{message.from_user.id}")
        ]])
        await bot.send_message(
            to_id,
            f"💬 <b>YANGI XABAR!</b>\n\n"
            f"Yuboruvchi: {from_name}\n"
            f"Xabar: <i>{message.text}</i>",
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        logger.error(f"❌ Notification: {e}")
    
    await state.clear()

@dp.message(F.text == "💬 Xabarlar")
async def cmd_messages(message: types.Message, state: FSMContext):
    await state.clear()
    contacts = await get_contacts(message.from_user.id)
    
    if not contacts:
        await message.answer("📭 Kontakt yo'q.", reply_markup=main_kb())
        return
    
    await message.answer("💬 <b>KONTAKTLAR:</b>", parse_mode="HTML")
    
    for contact_id, in contacts:
        contact = await db_get(contact_id)
        if not contact:
            continue
        
        _, uname, fname, rank, roles = contact[:5]
        contact_name = fname or f"@{uname}" or "Foydalanuvchi"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Chat", callback_data=f"view_chat:{contact_id}"),
            InlineKeyboardButton(text="📝 Xabar", callback_data=f"send_msg:{contact_id}"),
        ]])
        
        await message.answer(
            f"👤 <b>{contact_name}</b>\n"
            f"{re(rank)} {rank}  🎮 {format_roles(roles)}",
            parse_mode="HTML",
            reply_markup=kb
        )

@dp.callback_query(F.data.startswith("view_chat:"))
async def cb_view_chat(call: types.CallbackQuery):
    contact_id = int(call.data.split(":")[1])
    messages = await get_messages(call.from_user.id, contact_id)
    
    contact = await db_get(contact_id)
    if not contact:
        await call.answer("❌ Topilmadi!", show_alert=True)
        return
    
    contact_name = contact[2] or f"@{contact[1]}" or "Foydalanuvchi"
    
    if not messages:
        await call.answer(f"📭 {contact_name} bilan xabar yo'q", show_alert=True)
        return
    
    msg_text = f"💬 <b>{contact_name}</b> SUHBAT:\n"
    msg_text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for msg_id, from_id, text, timestamp in messages:
        sender = "👤 Siz" if from_id == call.from_user.id else f"👥 {contact_name}"
        msg_text += f"{sender}: {text}\n\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📝 Javob", callback_data=f"send_msg:{contact_id}"),
    ]])
    
    await call.message.answer(msg_text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "announce_duo")
@dp.message(F.text == "📢 E'lon berish")
async def cmd_announce(message_or_call, state: FSMContext):
    await state.clear()
    
    if isinstance(message_or_call, types.CallbackQuery):
        user_id = message_or_call.from_user.id
        target = message_or_call.message
        await message_or_call.answer()
    else:
        user_id = message_or_call.from_user.id
        target = message_or_call
    
    u = await db_get(user_id)
    if not u or not is_profile_complete(u[3], u[4]):
        await target.answer(
            "⚠️ Profilingiz to'liq bo'lishi kerak.",
            reply_markup=main_kb()
        )
        return
    
    _, uname, fname, rank, roles = u[:5]
    login = f"@{uname}" if uname else fname or "NoName"
    
    await target.answer(
        f"📢 <b>E'LON BERISH?</b>\n\n"
        f"👤 {fname or login}\n"
        f"{re(rank)} {rank}\n"
        f"🎮 {format_roles(roles)}\n\n"
        f"💡 E'lon berilsa, sherik izlayotganlar sizi topib xabar yuborishi mumkin!",
        parse_mode="HTML",
        reply_markup=announce_kb()
    )

@dp.callback_query(F.data == "confirm_announce")
async def cb_announce_ok(call: types.CallbackQuery):
    u = await db_get(call.from_user.id)
    if not u:
        await call.answer("❌ Topilmadi!", show_alert=True)
        return
    
    _, uname, fname, rank, roles = u[:5]
    roles_list = json.loads(roles) if roles else []
    
    success = await add_announcement(call.from_user.id, rank, roles_list)
    
    if not success:
        await call.answer("❌ Xatosi!", show_alert=True)
        return
    
    await call.message.edit_text("✅ E'LON BERILDI!")
    await call.answer("✅ OK!")
    
    await asyncio.sleep(0.3)
    await send_profile(call.message, call.from_user.id)

@dp.callback_query(F.data == "delete_announce")
async def cb_delete_announce(call: types.CallbackQuery):
    success = await delete_announcement(call.from_user.id)
    
    if not success:
        await call.answer("❌ Xato!", show_alert=True)
        return
    
    await call.message.edit_text("❌ E'LON O'CHIRILDI!")
    await call.answer("✅ O'chirildi!")
    
    await asyncio.sleep(0.3)
    await send_profile(call.message, call.from_user.id)

@dp.message(Command("help"))
@dp.message(F.text == "❓ Yordam")
async def cmd_help(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📖 <b>QOʻLLANMA</b>\n\n"
        "👤 <b>Profil</b> — Rank + rollar, e'lon boshqarish\n"
        "🔍 <b>Sherik topish</b> — E'lon bergan sheriklar\n"
        "📢 <b>E'lon berish</b> — Sherik izlatish uchun e'lon\n"
        "💬 <b>Xabarlar</b> — Chat va kontaktlar\n\n"
        f"<b>🏆 RANKLAR:</b> {', '.join(RANKS)}\n"
        f"<b>🎮 ROLLAR:</b> {', '.join(ROLES)}\n\n"
        "<b>💡 MASLAHAT:</b> Sherik topish uchun avval e'lon bering!",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    # Faqat admin uchun
    ADMIN_ID = 7509257102  # Sizning Telegram ID
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun!")
        return
    
    await message.answer(
        "🔧 ADMIN PANEL\n\n"
        "/stats - Statistika\n"
        "/users - Foydalanuvchilar\n"
        "/backup - Backup"
    )

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    ADMIN_ID =  7509257102
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun!")
        return
    
    try:
        async with aiosqlite.connect(DB) as db:
            # Foydalanuvchilar soni
            cur = await db.execute("SELECT COUNT(*) FROM users")
            users = await cur.fetchone()
            
            # Xabarlar soni
            cur = await db.execute("SELECT COUNT(*) FROM messages")
            messages = await cur.fetchone()
            
            # E'lonlar soni
            cur = await db.execute("SELECT COUNT(*) FROM announcements")
            announcements = await cur.fetchone()
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
        return
    
    await message.answer(
        f"📊 STATISTIKA\n\n"
        f"👥 Foydalanuvchilar: {users[0]}\n"
        f"💬 Xabarlar: {messages[0]}\n"
        f"📢 E'lonlar: {announcements[0]}"
    )
@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    ADMIN_ID = 7509257102
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun!")
        return
    
    try:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT user_id, full_name, rank FROM users LIMIT 20")
            users = await cur.fetchall()
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
        return
    
    text = "👥 <b>FOYDALANUVCHILAR (Birinchi 20ta):</b>\n\n"
    for user_id, fname, rank in users:
        text += f"🔹 {fname or 'Anonim'} ({user_id})\n   Rank: {rank}\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("backup"))
async def cmd_backup(message: types.Message):
    ADMIN_ID = 7509257102
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun!")
        return
    
    try:
        import shutil
        backup_file = f"mlbb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy(DB, backup_file)
        
        await message.answer(
            f"✅ <b>BACKUP YARATILDI!</b>\n\n"
            f"Fayl: {backup_file}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
@dp.callback_query(F.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Bekor.")
    await call.answer()

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor.", reply_markup=main_kb())

@dp.message()
async def unknown(message: types.Message, state: FSMContext):
    cur = await state.get_state()
    if cur:
        await state.clear()
    await message.answer(
        "❓ Tanilmadi.",
        reply_markup=main_kb()
    )

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
async def main():
    await init_db()
    logger.info("✅ Database initialized")
    logger.info("✅ BOT ISHGA TUSHDI!")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
