"""
MLBB Duo Finder Bot - Railway Production Package

Features:
- Multi-admin support
- Persistent SQLite (Railway volume friendly)
- Required channel/group membership with expiration
- Scheduled ads with repeat interval and auto-expire
- Profile setup, duo search, announcements, messaging
- Admin panel: users, block/unblock, audits, req check, backup, characters

Install:
  pip install -r requirements.txt
Run:
  python mlbb_bot_updated.py
"""

import asyncio
import html
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "")
DB = os.getenv("DATABASE", "/data/mlbb.db")

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()}

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env ga BOT_TOKEN kiriting.")

if not ADMIN_IDS:
    # Backward-compatible fallback for old envs.
    fallback = os.getenv("ADMIN_ID", "")
    if fallback.isdigit():
        ADMIN_IDS.add(int(fallback))

if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS topilmadi. .env ga ADMIN_IDS=123,456 yozing.")


bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
ad_worker_task = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


RANKS = [
    "Warrior",
    "Elite",
    "Master",
    "Grandmaster",
    "Epic",
    "Legend",
    "Mythic",
    "Mythical Glory",
]
RANK_EMOJI = {
    "Warrior": "⚔️",
    "Elite": "🛡️",
    "Master": "🔮",
    "Grandmaster": "💎",
    "Epic": "🌟",
    "Legend": "👑",
    "Mythic": "🔱",
    "Mythical Glory": "🏆",
}
ROLES = ["Roamer", "Gold Lane", "Exp Lane", "Mid Lane", "Jungler"]
ROLE_EMOJI = {
    "Roamer": "🗺️",
    "Gold Lane": "💰",
    "Exp Lane": "⚡",
    "Mid Lane": "🎯",
    "Jungler": "🌲",
}


class Setup(StatesGroup):
    rank = State()
    roles = State()
    finding_rank = State()
    finding_roles = State()


class Messaging(StatesGroup):
    typing_message = State()


class AdminMessaging(StatesGroup):
    typing_message = State()


class CharacterAdd(StatesGroup):
    name = State()
    role = State()
    description = State()
    video_url = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def dt_to_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def str_to_dt(raw: str | None):
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def parse_hhmmss_to_seconds(raw: str):
    text = (raw or "").strip().replace(":", ".")
    parts = text.split(".")
    if len(parts) != 3:
        return None
    try:
        hh, mm, ss = int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return None
    if hh < 0 or not (0 <= mm <= 59) or not (0 <= ss <= 59):
        return None
    return hh * 3600 + mm * 60 + ss


def rank_emoji(rank: str) -> str:
    return RANK_EMOJI.get(rank, "🏅")


def role_emoji(role: str) -> str:
    return ROLE_EMOJI.get(role, "🎮")


def format_roles(roles_value) -> str:
    try:
        if isinstance(roles_value, str):
            roles = json.loads(roles_value) if roles_value else []
        else:
            roles = roles_value or []
        return "  ".join(f"{role_emoji(r)} {r}" for r in roles) if roles else "Tanlanmagan"
    except Exception:
        return "Xato"


def profile_complete(rank: str, roles_value) -> bool:
    if rank in (None, "", "Unranked"):
        return False
    try:
        if isinstance(roles_value, str):
            roles = json.loads(roles_value) if roles_value else []
        else:
            roles = roles_value or []
        return len(roles) > 0
    except Exception:
        return False


def chat_id_value(chat_id: str):
    try:
        return int(str(chat_id).strip())
    except Exception:
        return str(chat_id).strip()


def username_from_link(link: str):
    if "t.me/" not in (link or ""):
        return None
    tail = link.split("t.me/", 1)[1].strip().strip("/")
    if not tail or tail.startswith("+") or tail.startswith("joinchat"):
        return None
    return f"@{tail.split('/', 1)[0].split('?', 1)[0]}"


def is_bot_block_error(exc: Exception) -> bool:
    t = str(exc).lower()
    return "bot was blocked by the user" in t or ("forbidden" in t and "bot" in t)


@asynccontextmanager
async def connect_db():
    db = await aiosqlite.connect(DB)
    try:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute("PRAGMA busy_timeout=5000;")
        yield db
    finally:
        await db.close()


async def init_db():
    async with connect_db() as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                rank TEXT DEFAULT 'Unranked',
                roles TEXT DEFAULT '[]',
                looking_for_rank TEXT DEFAULT 'Unranked',
                looking_for_roles TEXT DEFAULT '[]',
                last_activity DATETIME,
                bot_blocked INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id INTEGER NOT NULL,
                to_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS announcements (
                announce_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                rank TEXT NOT NULL,
                roles TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS announcement_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                rank TEXT,
                roles TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY,
                reason TEXT DEFAULT 'Noma''lum',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                char_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                description TEXT NOT NULL,
                video_url TEXT DEFAULT ''
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                total_games INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                playtime_mins INTEGER DEFAULT 0,
                last_match DATETIME,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_name TEXT NOT NULL,
                badge_emoji TEXT DEFAULT '🏅',
                earned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, badge_name)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS match_history (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                partner_id INTEGER,
                result TEXT,
                duo_rank TEXT,
                duo_roles TEXT,
                notes TEXT DEFAULT '',
                match_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS search_preferences (
                pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                region TEXT DEFAULT 'any',
                language TEXT DEFAULT 'uz',
                skill_level TEXT DEFAULT 'any',
                min_win_rate INTEGER DEFAULT 0,
                playtime_pref TEXT DEFAULT 'any',
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS leaderboard_cache (
                cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                rank_pos INTEGER,
                metric_type TEXT,
                metric_value REAL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS required_chats (
                req_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL UNIQUE,
                title TEXT DEFAULT '',
                invite_link TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ad_config (
                config_id INTEGER PRIMARY KEY CHECK (config_id = 1),
                ad_text TEXT DEFAULT '',
                is_active INTEGER DEFAULT 0,
                repeat_seconds INTEGER DEFAULT 0,
                start_at DATETIME,
                end_at DATETIME,
                last_sent_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            "INSERT OR IGNORE INTO ad_config (config_id, ad_text, is_active) VALUES (1, '', 0)"
        )

        # Old DB migration (missing columns).
        for col_def in ["last_activity DATETIME", "bot_blocked INTEGER DEFAULT 0"]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            except Exception:
                pass

        await db.commit()


# -------------------- DB helpers --------------------
async def mark_user_activity(user: types.User):
    async with connect_db() as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_activity, bot_blocked)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_activity=CURRENT_TIMESTAMP,
                bot_blocked=0,
                updated_at=CURRENT_TIMESTAMP
            """,
            (user.id, user.username or "", user.full_name or ""),
        )
        await db.commit()


async def mark_user_bot_blocked(user_id: int, blocked: bool):
    async with connect_db() as db:
        await db.execute("UPDATE users SET bot_blocked=? WHERE user_id=?", (1 if blocked else 0, user_id))
        await db.commit()


async def db_get_user(user_id: int):
    async with connect_db() as db:
        cur = await db.execute(
            "SELECT user_id, username, full_name, rank, roles, looking_for_rank, looking_for_roles FROM users WHERE user_id=?",
            (user_id,),
        )
        return await cur.fetchone()


async def db_save_user(
    user_id: int,
    username: str,
    full_name: str,
    rank=None,
    roles=None,
    looking_for_rank=None,
    looking_for_roles=None,
):
    row = await db_get_user(user_id)
    new_rank = rank if rank else (row[3] if row else "Unranked")
    new_roles = roles if roles is not None else (json.loads(row[4]) if row and row[4] else [])
    new_looking_rank = looking_for_rank if looking_for_rank else (row[5] if row else "Unranked")
    new_looking_roles = looking_for_roles if looking_for_roles is not None else (json.loads(row[6]) if row and row[6] else [])
    async with connect_db() as db:
        if row:
            await db.execute(
                "UPDATE users SET username=?, full_name=?, rank=?, roles=?, looking_for_rank=?, "
                "looking_for_roles=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (username, full_name, new_rank, json.dumps(new_roles), new_looking_rank, json.dumps(new_looking_roles), user_id),
            )
        else:
            await db.execute(
                "INSERT INTO users (user_id, username, full_name, rank, roles, looking_for_rank, looking_for_roles) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, full_name, new_rank, json.dumps(new_roles), new_looking_rank, json.dumps(new_looking_roles)),
            )
            await db.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,))
        await db.commit()


async def save_message(from_id: int, to_id: int, text: str):
    async with connect_db() as db:
        await db.execute("INSERT INTO messages (from_id, to_id, text) VALUES (?, ?, ?)", (from_id, to_id, text))
        await db.commit()


async def get_contacts(user_id: int):
    async with connect_db() as db:
        cur = await db.execute(
            """
            SELECT contact_id, MAX(timestamp) AS last_ts
            FROM (
                SELECT CASE WHEN from_id=? THEN to_id ELSE from_id END AS contact_id, timestamp
                FROM messages
                WHERE from_id=? OR to_id=?
            )
            GROUP BY contact_id
            ORDER BY last_ts DESC
            """,
            (user_id, user_id, user_id),
        )
        return await cur.fetchall()


async def get_messages(a: int, b: int):
    async with connect_db() as db:
        cur = await db.execute(
            "SELECT msg_id, from_id, text, timestamp FROM messages "
            "WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) ORDER BY timestamp ASC",
            (a, b, b, a),
        )
        return await cur.fetchall()


async def add_announcement(user_id: int, rank: str, roles: list[str]):
    async with connect_db() as db:
        await db.execute("DELETE FROM announcements WHERE user_id=?", (user_id,))
        await db.execute(
            "INSERT INTO announcements (user_id, rank, roles) VALUES (?, ?, ?)",
            (user_id, rank, json.dumps(roles)),
        )
        await db.execute(
            "INSERT INTO announcement_logs (user_id, action, rank, roles) VALUES (?, 'create', ?, ?)",
            (user_id, rank, json.dumps(roles)),
        )
        await db.commit()


async def delete_announcement(user_id: int):
    async with connect_db() as db:
        cur = await db.execute("SELECT rank, roles FROM announcements WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        await db.execute("DELETE FROM announcements WHERE user_id=?", (user_id,))
        if row:
            await db.execute(
                "INSERT INTO announcement_logs (user_id, action, rank, roles) VALUES (?, 'delete', ?, ?)",
                (user_id, row[0], row[1]),
            )
        await db.commit()


async def get_user_announcement(user_id: int):
    async with connect_db() as db:
        cur = await db.execute("SELECT announce_id, rank, roles FROM announcements WHERE user_id=?", (user_id,))
        return await cur.fetchone()


async def find_duos(rank: str, roles: list[str]):
    idx = RANKS.index(rank)
    nearby = [RANKS[i] for i in range(max(0, idx - 1), min(len(RANKS), idx + 2))]
    placeholders = ",".join("?" * len(nearby))
    async with connect_db() as db:
        cur = await db.execute(
            f"SELECT user_id, rank, roles FROM announcements WHERE rank IN ({placeholders}) ORDER BY timestamp DESC",
            nearby,
        )
        rows = await cur.fetchall()
    out = []
    for uid, rnk, roles_json in rows:
        try:
            rr = json.loads(roles_json or "[]")
        except Exception:
            rr = []
        if any(x in rr for x in roles):
            u = await db_get_user(uid)
            if u:
                out.append((uid, u[1], u[2], rnk, rr))
    return out


async def is_blacklisted(user_id: int):
    if is_admin(user_id):
        return False
    async with connect_db() as db:
        cur = await db.execute("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,))
        return (await cur.fetchone()) is not None


async def add_to_blacklist(user_id: int, reason: str):
    async with connect_db() as db:
        await db.execute("INSERT OR REPLACE INTO blacklist (user_id, reason) VALUES (?, ?)", (user_id, reason))
        await db.commit()


async def remove_from_blacklist(user_id: int):
    async with connect_db() as db:
        await db.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
        await db.commit()


async def get_blacklist_rows():
    async with connect_db() as db:
        cur = await db.execute("SELECT user_id, reason, timestamp FROM blacklist ORDER BY timestamp DESC")
        return await cur.fetchall()


async def get_user_stats(user_id: int):
    async with connect_db() as db:
        cur = await db.execute(
            "SELECT total_games, total_wins, total_losses, win_rate, playtime_mins FROM user_stats WHERE user_id=?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,))
            await db.commit()
            return 0, 0, 0, 0.0, 0
        return row


async def init_user_stats(user_id: int):
    """user_stats da yo'q bo'lsa INSERT qiladi"""
    try:
        async with connect_db() as db:
            cur = await db.execute("SELECT user_id FROM user_stats WHERE user_id=?", (user_id,))
            if await cur.fetchone() is None:
                await db.execute("INSERT INTO user_stats (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return True
    except Exception as e:
        logger.error(f"init_user_stats error: {e}")
    return False


async def get_duo_games_count(user_id: int) -> int:
    """match_history da partner_id bor o'yinlar sonini qaytaradi"""
    try:
        async with connect_db() as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM match_history WHERE user_id=? AND partner_id IS NOT NULL",
                (user_id,),
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)
    except Exception as e:
        logger.error(f"get_duo_games_count error: {e}")
        return 0


BADGES = {
    "new_player": {"emoji": "🆕", "talab": "birinchi o'yin"},
    "starter": {"emoji": "🚀", "talab": "10+ o'yin"},
    "experienced": {"emoji": "⭐", "talab": "50+ o'yin"},
    "veteran": {"emoji": "👑", "talab": "100+ o'yin"},
    "legend": {"emoji": "🔱", "talab": "250+ o'yin"},
    "high_winrate": {"emoji": "🎯", "talab": "20+ o'yin va >=70% win rate"},
    "duo_master": {"emoji": "👥", "talab": "50+ duo o'yin"},
}


async def add_achievement(user_id: int, badge_name: str, emoji: str = "🏅"):
    """achievements ga INSERT OR IGNORE qiladi"""
    try:
        async with connect_db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO achievements (user_id, badge_name, badge_emoji) VALUES (?, ?, ?)",
                (user_id, badge_name, emoji),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"add_achievement error: {e}")
        return False


async def check_and_award_achievements(user_id: int) -> list[str]:
    """Chegaralarga qarab badge beradi va yangi berilgan ro'yxatni qaytaradi"""
    try:
        total_games, _wins, _losses, win_rate, _play = await get_user_stats(user_id)
        duo_games = await get_duo_games_count(user_id)
        awarded = []

        if total_games == 1:
            await add_achievement(user_id, "new_player", BADGES["new_player"]["emoji"])
            awarded.append("new_player")
        if total_games >= 10:
            await add_achievement(user_id, "starter", BADGES["starter"]["emoji"])
            awarded.append("starter")
        if total_games >= 50:
            await add_achievement(user_id, "experienced", BADGES["experienced"]["emoji"])
            awarded.append("experienced")
        if total_games >= 100:
            await add_achievement(user_id, "veteran", BADGES["veteran"]["emoji"])
            awarded.append("veteran")
        if total_games >= 250:
            await add_achievement(user_id, "legend", BADGES["legend"]["emoji"])
            awarded.append("legend")
        if total_games >= 20 and win_rate >= 70:
            await add_achievement(user_id, "high_winrate", BADGES["high_winrate"]["emoji"])
            awarded.append("high_winrate")
        if duo_games >= 50:
            await add_achievement(user_id, "duo_master", BADGES["duo_master"]["emoji"])
            awarded.append("duo_master")
        return awarded
    except Exception as e:
        logger.error(f"check_and_award_achievements error: {e}")
        return []


async def record_match(user_id: int, partner_id: int, result: str, duo_rank: str, duo_roles: list[str]) -> bool:
    """
    1) match_history insert
    2) user_stats update
    3) achievements check
    """
    try:
        async with connect_db() as db:
            await db.execute(
                "INSERT INTO match_history (user_id, partner_id, result, duo_rank, duo_roles) VALUES (?, ?, ?, ?, ?)",
                (user_id, partner_id, result, duo_rank, json.dumps(duo_roles)),
            )

            cur = await db.execute(
                "SELECT total_games, total_wins, total_losses FROM user_stats WHERE user_id=?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row is None:
                await db.execute("INSERT INTO user_stats (user_id) VALUES (?)", (user_id,))
                total_games, total_wins, total_losses = 0, 0, 0
            else:
                total_games, total_wins, total_losses = row

            total_games += 1
            if result == "win":
                total_wins += 1
            else:
                total_losses += 1
            win_rate = (total_wins / total_games * 100) if total_games > 0 else 0

            await db.execute(
                "UPDATE user_stats SET total_games=?, total_wins=?, total_losses=?, win_rate=?, "
                "updated_date=CURRENT_TIMESTAMP WHERE user_id=?",
                (total_games, total_wins, total_losses, win_rate, user_id),
            )
            await db.commit()

        await check_and_award_achievements(user_id)
        return True
    except Exception as e:
        logger.error(f"record_match error: {e}")
        return False


async def get_match_history(user_id: int, limit: int = 10):
    """match_history dan oxirgi N qatorni qaytaradi"""
    try:
        async with connect_db() as db:
            cur = await db.execute(
                "SELECT match_id, partner_id, result, duo_rank, match_date FROM match_history "
                "WHERE user_id=? ORDER BY match_date DESC LIMIT ?",
                (user_id, limit),
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_match_history error: {e}")
        return []


async def get_user_achievements(user_id: int):
    async with connect_db() as db:
        cur = await db.execute(
            "SELECT badge_name, badge_emoji, earned_date FROM achievements WHERE user_id=? ORDER BY earned_date DESC",
            (user_id,),
        )
        return await cur.fetchall()


async def get_leaderboard(metric: str = "total_games", limit: int = 10):
    async with connect_db() as db:
        if metric == "win_rate":
            cur = await db.execute(
                "SELECT user_id, total_games, win_rate FROM user_stats "
                "WHERE total_games >= 20 ORDER BY win_rate DESC LIMIT ?",
                (limit,),
            )
        else:
            cur = await db.execute(
                "SELECT user_id, total_games, win_rate FROM user_stats "
                "WHERE total_games > 0 ORDER BY total_games DESC LIMIT ?",
                (limit,),
            )
        return await cur.fetchall()


async def get_user_message_audit(user_id: int, limit: int = 10):
    async with connect_db() as db:
        sent = await (
            await db.execute(
                "SELECT to_id, text, timestamp FROM messages WHERE from_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            )
        ).fetchall()
        recv = await (
            await db.execute(
                "SELECT from_id, text, timestamp FROM messages WHERE to_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            )
        ).fetchall()
        return sent, recv


async def get_announcement_logs(user_id: int, limit: int = 20):
    async with connect_db() as db:
        cur = await db.execute(
            "SELECT action, rank, roles, timestamp FROM announcement_logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        )
        return await cur.fetchall()


async def clear_user_messages(user_id: int):
    try:
        async with connect_db() as db:
            cur = await db.execute("SELECT COUNT(*) FROM messages WHERE from_id=? OR to_id=?", (user_id, user_id))
            total = int((await cur.fetchone())[0])
            await db.execute("DELETE FROM messages WHERE from_id=? OR to_id=?", (user_id, user_id))
            await db.commit()
            return True, total
    except Exception as e:
        logger.error(f"clear_user_messages error: {e}")
        return False, 0


# Required chats
async def cleanup_expired_required_chats():
    async with connect_db() as db:
        await db.execute(
            "DELETE FROM required_chats WHERE expires_at IS NOT NULL AND datetime(expires_at) <= datetime('now')"
        )
        await db.commit()


async def get_required_chats(active_only: bool = True):
    await cleanup_expired_required_chats()
    async with connect_db() as db:
        if active_only:
            cur = await db.execute(
                "SELECT chat_id, title, invite_link, expires_at FROM required_chats "
                "WHERE is_active=1 ORDER BY req_id ASC"
            )
        else:
            cur = await db.execute(
                "SELECT chat_id, title, invite_link, is_active, expires_at FROM required_chats ORDER BY req_id ASC"
            )
        return await cur.fetchall()


async def resolve_chat_id(chat_id: str, invite_link: str):
    try:
        chat = await bot.get_chat(chat_id_value(chat_id))
        return str(chat.id)
    except Exception:
        pass
    uname = username_from_link(invite_link)
    if uname:
        try:
            chat = await bot.get_chat(uname)
            return str(chat.id)
        except Exception:
            return None
    return None


async def add_required_chat(chat_id: str, invite_link: str, title: str, days: int):
    normalized = await resolve_chat_id(chat_id, invite_link)
    if not normalized:
        return False, "CHAT_ID yoki link noto'g'ri. /chat_id yoki /get_chat_id bilan tekshiring."
    expires = dt_to_str(now_utc() + timedelta(days=max(1, days)))
    async with connect_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO required_chats (chat_id, title, invite_link, is_active, expires_at) VALUES (?, ?, ?, 1, ?)",
            (normalized, title, invite_link, expires),
        )
        await db.commit()
    return True, normalized


async def remove_required_chat(chat_id: str):
    async with connect_db() as db:
        await db.execute("DELETE FROM required_chats WHERE chat_id=?", (chat_id.strip(),))
        await db.commit()


async def get_missing_required_chats(user_id: int):
    missing = []
    for chat_id, title, invite_link, _exp in await get_required_chats(active_only=True):
        try:
            m = await bot.get_chat_member(chat_id=chat_id_value(chat_id), user_id=user_id)
            if m.status not in ("member", "administrator", "creator"):
                missing.append((chat_id, title, invite_link))
        except Exception:
            missing.append((chat_id, title, invite_link))
    return missing


async def debug_required_for_user(user_id: int):
    rows = []
    for chat_id, title, invite_link, exp in await get_required_chats(active_only=True):
        try:
            m = await bot.get_chat_member(chat_id=chat_id_value(chat_id), user_id=user_id)
            rows.append((chat_id, title, invite_link, exp, m.status, ""))
        except Exception as e:
            rows.append((chat_id, title, invite_link, exp, "unknown", str(e)))
    return rows


# Ads
async def set_ad_schedule(text: str, days: int, repeat_seconds: int):
    start = now_utc()
    end = start + timedelta(days=max(1, days))
    async with connect_db() as db:
        await db.execute(
            """
            UPDATE ad_config
            SET ad_text=?, is_active=1, repeat_seconds=?, start_at=?, end_at=?, last_sent_at=NULL,
                updated_at=CURRENT_TIMESTAMP
            WHERE config_id=1
            """,
            (text, repeat_seconds, dt_to_str(start), dt_to_str(end)),
        )
        await db.commit()


async def clear_ad_config():
    async with connect_db() as db:
        await db.execute(
            "UPDATE ad_config SET ad_text='', is_active=0, repeat_seconds=0, start_at=NULL, end_at=NULL, last_sent_at=NULL WHERE config_id=1"
        )
        await db.commit()


async def set_ad_status(active: bool):
    async with connect_db() as db:
        await db.execute("UPDATE ad_config SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE config_id=1", (1 if active else 0,))
        await db.commit()


async def get_active_ad_config():
    async with connect_db() as db:
        cur = await db.execute(
            "SELECT ad_text, is_active, repeat_seconds, start_at, end_at, last_sent_at FROM ad_config WHERE config_id=1"
        )
        row = await cur.fetchone()
    if not row:
        return None
    ad_text, is_active, repeat_seconds, start_at, end_at, last_sent_at = row
    if is_active != 1 or not (ad_text or "").strip():
        return None
    end_dt = str_to_dt(end_at)
    if end_dt and now_utc() >= end_dt:
        await clear_ad_config()
        return None
    return {
        "ad_text": ad_text.strip(),
        "repeat_seconds": int(repeat_seconds or 0),
        "start_at": start_at,
        "end_at": end_at,
        "last_sent_at": last_sent_at,
    }


async def mark_ad_sent_now():
    async with connect_db() as db:
        await db.execute("UPDATE ad_config SET last_sent_at=?, updated_at=CURRENT_TIMESTAMP WHERE config_id=1", (dt_to_str(now_utc()),))
        await db.commit()


async def broadcast_ad(ad_text: str):
    sent = 0
    text = f"📢 <b>REKLAMA</b>\n\n{html.escape(ad_text)}"
    async with connect_db() as db:
        rows = await (await db.execute("SELECT user_id FROM users")).fetchall()
    for (uid,) in rows:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            await mark_user_bot_blocked(uid, False)
            sent += 1
        except Exception as e:
            if is_bot_block_error(e):
                await mark_user_bot_blocked(uid, True)
    return sent


async def ad_worker_loop():
    while True:
        try:
            cfg = await get_active_ad_config()
            if cfg and cfg["repeat_seconds"] > 0:
                last_dt = str_to_dt(cfg.get("last_sent_at"))
                if (not last_dt) or (now_utc() - last_dt).total_seconds() >= cfg["repeat_seconds"]:
                    await broadcast_ad(cfg["ad_text"])
                    await mark_ad_sent_now()
        except Exception as e:
            logger.error(f"ad_worker_loop error: {e}")
        await asyncio.sleep(2)


# -------------------- Keyboards --------------------
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Profil"), KeyboardButton(text="🔍 Sherik topish")],
            [KeyboardButton(text="📢 E'lon berish"), KeyboardButton(text="💬 Xabarlar")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📚 MLBB haqida")],
            [KeyboardButton(text="❓ Yordam"), KeyboardButton(text="📞 Admin bilan bog'lanish")],
        ],
        resize_keyboard=True,
    )


def rank_kb():
    rows, row = [], []
    for r in RANKS:
        row.append(InlineKeyboardButton(text=f"{rank_emoji(r)} {r}", callback_data=f"rank:{r}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def roles_kb(prefix: str, selected=None):
    selected = selected or []
    rows = []
    for i, r in enumerate(ROLES):
        if i % 2 == 0:
            row = []
        mark = "☑️" if r in selected else "☐"
        row.append(InlineKeyboardButton(text=f"{mark} {role_emoji(r)} {r}", callback_data=f"{prefix}:{r}"))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data=f"{prefix}:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_kb(with_delete: bool):
    rows = [
        [InlineKeyboardButton(text="✏️ Rank", callback_data="edit_rank"), InlineKeyboardButton(text="✏️ Rollar", callback_data="edit_roles")],
        [InlineKeyboardButton(text="🎮 Dost topish", callback_data="find_duo"), InlineKeyboardButton(text="📢 E'lon berish", callback_data="announce_duo")],
    ]
    if with_delete:
        rows.append([InlineKeyboardButton(text="❌ E'lonni o'chirish", callback_data="delete_announce")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def announce_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Ha", callback_data="confirm_announce"), InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")]]
    )


def mlbb_info_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Qahramonlar", callback_data="show_characters")],
            [InlineKeyboardButton(text="📖 MLBB haqida", callback_data="show_mlbb_info")],
            [InlineKeyboardButton(text="❌ Orqaga", callback_data="cancel")],
        ]
    )


def characters_roles_kb():
    rows = [[InlineKeyboardButton(text=f"{role_emoji(r)} {r}", callback_data=f"char_role:{r}")] for r in ROLES]
    rows.append([InlineKeyboardButton(text="❌ Orqaga", callback_data="mlbb_info")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def required_join_kb(missing):
    rows = []
    for chat_id, title, invite_link in missing:
        label = title.strip() if (title or "").strip() else str(chat_id)
        rows.append([InlineKeyboardButton(text=f"➕ {label}", url=invite_link)])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_join_status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions_kb(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Xabar yozish", callback_data=f"admin_user_msg:{user_id}"), InlineKeyboardButton(text="🔴 Blok qilish", callback_data=f"admin_user_block:{user_id}")],
            [InlineKeyboardButton(text="📝 Chat tarixi", callback_data=f"admin_user_chat:{user_id}"), InlineKeyboardButton(text="📢 E'lon tarixi", callback_data=f"admin_user_ann:{user_id}")],
            [InlineKeyboardButton(text="🟢 Unblock", callback_data=f"admin_user_unblock:{user_id}"), InlineKeyboardButton(text="📊 Stat", callback_data=f"admin_user_stat:{user_id}")],
            [InlineKeyboardButton(text="🔍 Req Check", callback_data=f"admin_user_req:{user_id}")],
            [InlineKeyboardButton(text="🗑 Xabarlarni tozalash", callback_data=f"admin_user_clear:{user_id}")],
        ]
    )


# -------------------- Middleware --------------------
class SecurityMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        if user and not is_admin(user.id):
            await mark_user_activity(user)
            if await is_blacklisted(user.id):
                try:
                    if isinstance(event, types.CallbackQuery):
                        await event.answer("Siz bloklangansiz", show_alert=True)
                    elif hasattr(event, "answer"):
                        await event.answer("🔴 Siz bloklangansiz")
                except Exception:
                    pass
                return

            cb_data = event.data if isinstance(event, types.CallbackQuery) else None
            if cb_data != "check_join_status":
                missing = await get_missing_required_chats(user.id)
                if missing:
                    text = (
                        "🔒 <b>Botdan foydalanish uchun required kanal/guruhlarga qo'shiling.</b>\n\n"
                        "Qo'shilgandan keyin Tekshirish tugmasini bosing."
                    )
                    kb = required_join_kb(missing)
                    try:
                        if isinstance(event, types.CallbackQuery):
                            await event.answer("Avval required chatlarga qo'shiling", show_alert=True)
                            await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
                        elif hasattr(event, "answer"):
                            await event.answer(text, parse_mode="HTML", reply_markup=kb)
                    except Exception:
                        pass
                    return

        return await handler(event, data)


# -------------------- User handlers --------------------
async def send_profile(target: types.Message, user_id: int):
    u = await db_get_user(user_id)
    if not u:
        await target.answer("❌ Profil topilmadi", reply_markup=main_kb())
        return
    _, uname, fname, rank, roles, _, looking_roles = u
    ann = await get_user_announcement(user_id)
    msg = (
        "👤 <b>PROFILINGIZ</b>\n"
        f"Ism: {html.escape(fname or '-')}\n"
        f"Login: {html.escape('@' + uname if uname else '-')}\n"
        f"Rank: {rank_emoji(rank)} <b>{rank}</b>\n"
        f"Rollar: {format_roles(roles)}\n"
        f"Qidirayotgan rollar: {format_roles(looking_roles)}\n"
        f"E'lon: {'✅ bor' if ann else '❌ yo\'q'}\n"
        f"Profil: {'✅ to\'liq' if profile_complete(rank, roles) else '⚠️ to\'liq emas'}"
    )
    await target.answer(msg, parse_mode="HTML", reply_markup=profile_kb(with_delete=bool(ann)))


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await db_save_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name or "")
    await init_user_stats(message.from_user.id)
    await message.answer(
        f"👋 Salom, <b>{html.escape(message.from_user.full_name or 'Foydalanuvchi')}</b>!\nMLBB Duo Finder botga xush kelibsiz.",
        parse_mode="HTML",
        reply_markup=main_kb(),
    )
    ad = await get_active_ad_config()
    if ad:
        await message.answer(f"📢 <b>REKLAMA</b>\n\n{html.escape(ad['ad_text'])}", parse_mode="HTML")
    u = await db_get_user(message.from_user.id)
    if not u or not profile_complete(u[3], u[4]):
        await message.answer("Profilni to'ldirish uchun rank tanlang:", reply_markup=rank_kb())
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
    await call.message.answer("🏆 Rank tanlang:", reply_markup=rank_kb())
    await call.answer()


@dp.callback_query(StateFilter(Setup.rank), F.data.startswith("rank:"))
async def cb_set_rank(call: types.CallbackQuery, state: FSMContext):
    rank = call.data.split(":", 1)[1]
    if rank not in RANKS:
        await call.answer("Noto'g'ri rank", show_alert=True)
        return
    await state.update_data(setup_rank=rank, setup_roles=[])
    await state.set_state(Setup.roles)
    await call.message.edit_text(f"✅ Rank: <b>{rank}</b>\nEndi rollarni tanlang:", parse_mode="HTML", reply_markup=roles_kb("setup_role", []))
    await call.answer()


@dp.callback_query(StateFilter(Setup.roles), F.data.startswith("setup_role:"))
async def cb_roles(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("setup_roles", [])
    if role == "done":
        if not selected:
            await call.answer("Kamida 1 rol tanlang", show_alert=True)
            return
        await db_save_user(
            call.from_user.id,
            call.from_user.username or "",
            call.from_user.full_name or "",
            rank=data.get("setup_rank"),
            roles=selected,
        )
        await state.clear()
        await call.message.edit_text("✅ Profil saqlandi")
        await send_profile(call.message, call.from_user.id)
        await call.answer()
        return
    if role in selected:
        selected.remove(role)
    else:
        selected.append(role)
    await state.update_data(setup_roles=selected)
    await call.message.edit_reply_markup(reply_markup=roles_kb("setup_role", selected))
    await call.answer()


@dp.callback_query(F.data == "edit_roles")
async def cb_edit_roles(call: types.CallbackQuery, state: FSMContext):
    u = await db_get_user(call.from_user.id)
    if not u:
        await call.answer("Profil topilmadi", show_alert=True)
        return
    roles = json.loads(u[4]) if u[4] else []
    await state.update_data(setup_rank=u[3], setup_roles=roles)
    await state.set_state(Setup.roles)
    await call.message.answer("Rollarni tanlang:", reply_markup=roles_kb("setup_role", roles))
    await call.answer()


@dp.message(F.text == "🔍 Sherik topish")
@dp.callback_query(F.data == "find_duo")
async def cmd_find(message_or_call, state: FSMContext):
    await state.clear()
    if isinstance(message_or_call, types.CallbackQuery):
        user_id = message_or_call.from_user.id
        target = message_or_call.message
        await message_or_call.answer()
    else:
        user_id = message_or_call.from_user.id
        target = message_or_call
    u = await db_get_user(user_id)
    if not u or not profile_complete(u[3], u[4]):
        await target.answer("Profil to'liq emas")
        return
    await state.set_state(Setup.finding_rank)
    await target.answer("Kerakli rank tanlang:", reply_markup=rank_kb())


@dp.callback_query(StateFilter(Setup.finding_rank), F.data.startswith("rank:"))
async def cb_find_rank(call: types.CallbackQuery, state: FSMContext):
    rank = call.data.split(":", 1)[1]
    await state.update_data(find_rank=rank, find_roles=[])
    await state.set_state(Setup.finding_roles)
    await call.message.edit_text(f"✅ Rank: {rank}\nEndi kerakli rollarni tanlang:", reply_markup=roles_kb("find_role", []))
    await call.answer()


@dp.callback_query(StateFilter(Setup.finding_roles), F.data.startswith("find_role:"))
async def cb_find_roles(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("find_roles", [])
    if role == "done":
        if not selected:
            await call.answer("Rol tanlang", show_alert=True)
            return
        matches = await find_duos(data.get("find_rank"), selected)
        if not matches:
            await call.message.edit_text("😔 Sherik topilmadi")
            await state.clear()
            return
        await call.message.edit_text(f"✅ Topildi: {len(matches)} ta")
        for uid, uname, fname, urank, uroles in matches:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Xabar", callback_data=f"send_msg:{uid}")]])
            await bot.send_message(
                call.from_user.id,
                f"👤 {html.escape(fname or ('@' + uname if uname else str(uid)))}\n{rank_emoji(urank)} {urank}\n{format_roles(uroles)}",
                parse_mode="HTML",
                reply_markup=kb,
            )
        await state.clear()
        await call.answer()
        return
    if role in selected:
        selected.remove(role)
    else:
        selected.append(role)
    await state.update_data(find_roles=selected)
    await call.message.edit_reply_markup(reply_markup=roles_kb("find_role", selected))
    await call.answer()


@dp.message(F.text == "📢 E'lon berish")
@dp.callback_query(F.data == "announce_duo")
async def cmd_announce(message_or_call, state: FSMContext):
    await state.clear()
    if isinstance(message_or_call, types.CallbackQuery):
        target = message_or_call.message
        user_id = message_or_call.from_user.id
        await message_or_call.answer()
    else:
        target = message_or_call
        user_id = message_or_call.from_user.id
    u = await db_get_user(user_id)
    if not u or not profile_complete(u[3], u[4]):
        await target.answer("Profil to'liq bo'lishi kerak")
        return
    await target.answer(
        f"E'lon berilsinmi?\n{rank_emoji(u[3])} {u[3]}\n{format_roles(u[4])}",
        reply_markup=announce_kb(),
    )


@dp.callback_query(F.data == "confirm_announce")
async def cb_confirm_announce(call: types.CallbackQuery):
    u = await db_get_user(call.from_user.id)
    if not u:
        await call.answer("Profil topilmadi", show_alert=True)
        return
    roles = json.loads(u[4]) if u[4] else []
    await add_announcement(call.from_user.id, u[3], roles)
    await call.message.edit_text("✅ E'lon berildi")
    await send_profile(call.message, call.from_user.id)
    await call.answer()


@dp.callback_query(F.data == "delete_announce")
async def cb_delete_announce(call: types.CallbackQuery):
    await delete_announcement(call.from_user.id)
    await call.message.edit_text("❌ E'lon o'chirildi")
    await send_profile(call.message, call.from_user.id)
    await call.answer()


@dp.callback_query(F.data.startswith("send_msg:"))
async def cb_send_msg(call: types.CallbackQuery, state: FSMContext):
    to_id = int(call.data.split(":", 1)[1])
    u = await db_get_user(to_id)
    if not u:
        await call.answer("User topilmadi", show_alert=True)
        return
    await state.update_data(msg_to_id=to_id, msg_to_name=u[2] or "Foydalanuvchi")
    await state.set_state(Messaging.typing_message)
    await call.message.answer(f"💬 {html.escape(u[2] or 'Foydalanuvchi')} ga yozing\n/cancel")
    await call.answer()


@dp.message(StateFilter(Messaging.typing_message))
async def on_send_msg(message: types.Message, state: FSMContext):
    data = await state.get_data()
    to_id = data.get("msg_to_id")
    if not to_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Bo'sh xabar yuborilmaydi")
        return
    await save_message(message.from_user.id, to_id, text)
    await message.answer("✅ Yuborildi", reply_markup=main_kb())
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Javob", callback_data=f"send_msg:{message.from_user.id}")]])
        await bot.send_message(
            to_id,
            f"💬 <b>Yangi xabar</b>\nKimdan: {html.escape(message.from_user.full_name or 'User')}\nXabar: <i>{html.escape(text)}</i>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await mark_user_bot_blocked(to_id, False)
    except Exception as e:
        logger.error(f"Notification error: {e}")
        if is_bot_block_error(e):
            await mark_user_bot_blocked(to_id, True)
    await state.clear()


@dp.message(F.text == "💬 Xabarlar")
async def cmd_messages(message: types.Message, state: FSMContext):
    await state.clear()
    contacts = await get_contacts(message.from_user.id)
    if not contacts:
        await message.answer("📭 Kontakt yo'q", reply_markup=main_kb())
        return
    for contact_id, _ in contacts:
        u = await db_get_user(contact_id)
        if not u:
            continue
        name = u[2] or ("@" + u[1] if u[1] else "Foydalanuvchi")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💬 Chat", callback_data=f"view_chat:{contact_id}"), InlineKeyboardButton(text="📝 Xabar", callback_data=f"send_msg:{contact_id}")]]
        )
        await message.answer(f"👤 <b>{html.escape(name)}</b>\n{rank_emoji(u[3])} {u[3]}\n{format_roles(u[4])}", parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("view_chat:"))
async def cb_view_chat(call: types.CallbackQuery):
    cid = int(call.data.split(":", 1)[1])
    msgs = await get_messages(call.from_user.id, cid)
    u = await db_get_user(cid)
    if not u:
        await call.answer("User topilmadi", show_alert=True)
        return
    name = u[2] or ("@" + u[1] if u[1] else "Foydalanuvchi")
    if not msgs:
        await call.answer("Xabarlar yo'q", show_alert=True)
        return
    text = [f"💬 <b>{html.escape(name)}</b> bilan suhbat", ""]
    for _, from_id, m, _ in msgs:
        sender = "Siz" if from_id == call.from_user.id else name
        text.append(f"{html.escape(sender)}: {html.escape(m)}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Javob", callback_data=f"send_msg:{cid}")]])
    await call.message.answer("\n".join(text), parse_mode="HTML", reply_markup=kb)
    await call.answer()


@dp.message(F.text == "📊 Statistika")
@dp.message(Command("mystats"))
async def cmd_stats_user(message: types.Message):
    g, w, l, wr, play = await get_user_stats(message.from_user.id)
    ach = await get_user_achievements(message.from_user.id)
    recent_matches = await get_match_history(message.from_user.id, limit=5)
    text = (
        "📊 <b>Sizning statistikangiz</b>\n"
        f"🎮 O'yinlar: {g}\n✅ G'alaba: {w}\n❌ Mag'lubiyat: {l}\n🎯 WinRate: {wr:.1f}%\n⏱️ Playtime: {play}"
    )
    if ach:
        text += "\n\n🎖️ Badge'lar:\n" + "\n".join(f"{e} {n}" for n, e, _ in ach[:10])
    if recent_matches:
        text += "\n\n🕘 Oxirgi 5 o'yin:\n"
        for _mid, partner_id, result, duo_rank, match_date in recent_matches:
            icon = "✅" if result == "win" else "❌"
            text += f"{icon} {duo_rank} | partner: {partner_id or '-'} | {match_date}\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏆 Leaderboard", callback_data="view_leaderboard")]])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "view_leaderboard")
async def cb_leaderboard(call: types.CallbackQuery):
    rows = await get_leaderboard("total_games", 10)
    if not rows:
        await call.answer("Bo'sh", show_alert=True)
        return
    lines = ["🏆 <b>Top 10</b>", ""]
    for i, (uid, games, wr) in enumerate(rows, 1):
        u = await db_get_user(uid)
        lines.append(f"{i}. {html.escape((u[2] if u else str(uid)))} - {games} o'yin ({wr:.1f}%)")
    await call.message.edit_text("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.message(F.text == "📚 MLBB haqida")
async def cmd_mlbb_menu(message: types.Message):
    await message.answer("📚 <b>MLBB HAQIDA</b>\n\nQuyidagidan tanlang", parse_mode="HTML", reply_markup=mlbb_info_kb())


@dp.callback_query(F.data == "mlbb_info")
async def cb_mlbb_info(call: types.CallbackQuery):
    await call.message.edit_text("📚 <b>MLBB HAQIDA</b>", parse_mode="HTML", reply_markup=mlbb_info_kb())
    await call.answer()


@dp.callback_query(F.data == "show_characters")
async def cb_show_characters(call: types.CallbackQuery):
    await call.message.edit_text("🎮 Rolni tanlang", parse_mode="HTML", reply_markup=characters_roles_kb())
    await call.answer()


async def get_characters_by_role(role: str):
    async with connect_db() as db:
        return await (
            await db.execute("SELECT char_id, name, role, description, video_url FROM characters WHERE role=? ORDER BY name ASC", (role,))
        ).fetchall()


async def get_all_characters():
    async with connect_db() as db:
        return await (
            await db.execute("SELECT char_id, name, role, description, video_url FROM characters ORDER BY role, name ASC")
        ).fetchall()


async def add_character(name: str, role: str, description: str, video_url: str):
    async with connect_db() as db:
        await db.execute("INSERT OR REPLACE INTO characters (name, role, description, video_url) VALUES (?, ?, ?, ?)", (name, role, description, video_url))
        await db.commit()


async def delete_character(char_id: int):
    async with connect_db() as db:
        await db.execute("DELETE FROM characters WHERE char_id=?", (char_id,))
        await db.commit()


@dp.callback_query(F.data.startswith("char_role:"))
async def cb_char_role(call: types.CallbackQuery):
    role = call.data.split(":", 1)[1]
    chars = await get_characters_by_role(role)
    if not chars:
        await call.message.edit_text(f"❌ {role} uchun qahramon topilmadi", reply_markup=characters_roles_kb())
        await call.answer()
        return
    rows = [[InlineKeyboardButton(text=f"👤 {name}", callback_data=f"char_detail:{cid}")] for cid, name, _, _, _ in chars]
    rows.append([InlineKeyboardButton(text="❌ Orqaga", callback_data="show_characters")])
    await call.message.edit_text(f"🎮 <b>{role}</b> qahramonlari", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@dp.callback_query(F.data.startswith("char_detail:"))
async def cb_char_detail(call: types.CallbackQuery):
    cid = int(call.data.split(":", 1)[1])
    target = None
    for c in await get_all_characters():
        if c[0] == cid:
            target = c
            break
    if not target:
        await call.answer("Topilmadi", show_alert=True)
        return
    _, name, role, desc, video = target
    rows = []
    if video:
        rows.append([InlineKeyboardButton(text="🎥 Video", url=video)])
    rows.append([InlineKeyboardButton(text="❌ Orqaga", callback_data=f"char_role:{role}")])
    await call.message.edit_text(
        f"👤 <b>{html.escape(name)}</b>\n🎮 Rol: {role}\n\n📝 {html.escape(desc)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@dp.callback_query(F.data == "show_mlbb_info")
async def cb_show_mlbb_info(call: types.CallbackQuery):
    await call.message.edit_text(
        "📖 <b>MLBB</b> - 5v5 MOBA o'yin.\n\n"
        "Ranklar: Warrior → ... → Mythical Glory\n"
        "Rollar: Roamer, Gold, Exp, Mid, Jungler",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Orqaga", callback_data="mlbb_info")]]),
    )
    await call.answer()


@dp.message(Command("help"))
@dp.message(F.text == "❓ Yordam")
async def cmd_help(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📖 <b>Qo'llanma</b>\n\n"
        "👤 Profil\n🔍 Sherik topish\n📢 E'lon berish\n💬 Xabarlar\n📊 Statistika",
        parse_mode="HTML",
        reply_markup=main_kb(),
    )


@dp.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin(message: types.Message):
    await message.answer("👨‍💻 Admin: @rSx_ravshanoff")


# -------------------- Admin handlers --------------------
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Faqat admin uchun")
        return
    await message.answer(
        "🔧 <b>ADMIN PANEL</b>\n\n"
        "/stats\n/users\n/blacklist\n/block <id> [sabab]\n/unblock <id>\n"
        "/admin_msg <id> <text>\n/audit_user <id>\n/announcement_history <id>\n"
        "/add_char\n/list_chars\n/del_char <id>\n/backup\n\n"
        "<b>Reklama</b>\n/set_ad KUN HH.MM.SS MATN\n/show_ad\n/ad_on\n/ad_off\n\n"
        "<b>Majburiy obuna</b>\n/req_add CHAT_ID LINK KUN [NOM]\n/req_remove CHAT_ID\n/req_list\n/req_check USER_ID\n/get_chat_id\n/chat_id",
        parse_mode="HTML",
    )


@dp.message(Command("stats"))
async def cmd_admin_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await cmd_stats_user(message)
        return
    async with connect_db() as db:
        users = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
        messages = await (await db.execute("SELECT COUNT(*) FROM messages")).fetchone()
        anns = await (await db.execute("SELECT COUNT(*) FROM announcements")).fetchone()
    await message.answer(f"👥 Users: {users[0]}\n💬 Messages: {messages[0]}\n📢 Announcements: {anns[0]}")


@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Faqat admin")
        return
    async with connect_db() as db:
        rows = await (
            await db.execute("SELECT user_id, full_name, rank, last_activity, bot_blocked FROM users ORDER BY updated_at DESC LIMIT 20")
        ).fetchall()
    if not rows:
        await message.answer("User yo'q")
        return
    await message.answer("👥 <b>Foydalanuvchilar (20 ta)</b>", parse_mode="HTML")
    for uid, fname, rank, last_activity, bot_blocked in rows:
        last_dt = str_to_dt(last_activity)
        if bot_blocked == 1:
            live = "⚫ Botdan chiqib ketgan"
        elif last_dt and (now_utc() - last_dt).total_seconds() <= 300:
            live = "🟢 Online"
        elif last_dt:
            live = "🟠 Offline"
        else:
            live = "⚪ Noma'lum"
        access = "🔴 BLOKLANGAN" if await is_blacklisted(uid) else "🟢 AKTIV"
        await message.answer(
            f"🔹 <b>{html.escape(fname or 'Anonim')}</b>\nID: <code>{uid}</code>\nRank: {rank}\nHolat: {access}\nFaollik: {live}",
            parse_mode="HTML",
            reply_markup=admin_user_actions_kb(uid),
        )


@dp.callback_query(F.data.startswith("admin_user_msg:"))
async def cb_admin_user_msg(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    u = await db_get_user(uid)
    if not u:
        await call.answer("Topilmadi", show_alert=True)
        return
    await state.set_state(AdminMessaging.typing_message)
    await state.update_data(admin_to_id=uid)
    await call.message.answer(f"💬 {html.escape(u[2] or 'Foydalanuvchi')} ga yozing\n/cancel")
    await call.answer()


@dp.message(StateFilter(AdminMessaging.typing_message))
async def admin_send_message(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("Bekor")
        return
    data = await state.get_data()
    to_id = data.get("admin_to_id")
    if not to_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Bo'sh xabar")
        return
    await save_message(message.from_user.id, to_id, f"[ADMIN] {text}")
    try:
        await bot.send_message(to_id, f"📩 <b>ADMIN XABARI</b>\n\n{html.escape(text)}", parse_mode="HTML")
        await mark_user_bot_blocked(to_id, False)
    except Exception as e:
        if is_bot_block_error(e):
            await mark_user_bot_blocked(to_id, True)
        await message.answer(f"⚠️ Yuborilmadi: {e}")
        await state.clear()
        return
    await message.answer("✅ Yuborildi")
    await state.clear()


@dp.callback_query(F.data.startswith("admin_user_block:"))
async def cb_admin_user_block(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    await add_to_blacklist(uid, "Admin paneldan bloklandi")
    await call.message.answer(f"🔴 Bloklandi: {uid}")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_unblock:"))
async def cb_admin_user_unblock(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    await remove_from_blacklist(uid)
    await call.message.answer(f"🟢 Unblock: {uid}")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_chat:"))
async def cb_admin_user_chat(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    sent, recv = await get_user_message_audit(uid)
    lines = [f"📝 <b>CHAT TARIXI</b> {uid}", "", "<b>Yuborganlari:</b>"]
    lines += [f"➡️ {to} | {ts}\n{html.escape(msg[:140])}" for to, msg, ts in sent] or ["Yo'q"]
    lines += ["", "<b>Olganlari:</b>"]
    lines += [f"⬅️ {fr} | {ts}\n{html.escape(msg[:140])}" for fr, msg, ts in recv] or ["Yo'q"]
    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_ann:"))
async def cb_admin_user_ann(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    rows = await get_announcement_logs(uid)
    if not rows:
        await call.message.answer("E'lon tarixi yo'q")
        await call.answer()
        return
    text = [f"📢 <b>E'LON TARIXI</b> {uid}", ""]
    for action, rank, roles, ts in rows:
        text.append(f"{ts} | {action} | {rank} | {html.escape(roles or '[]')}")
    await call.message.answer("\n".join(text), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_stat:"))
async def cb_admin_user_stat(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    g, w, l, wr, play = await get_user_stats(uid)
    ach = await get_user_achievements(uid)
    text = f"📊 <b>{uid}</b>\n🎮 {g}\n✅ {w}\n❌ {l}\n🎯 {wr:.1f}%\n⏱️ {play}"
    if ach:
        text += "\n\n" + "\n".join(f"{e} {n}" for n, e, _ in ach[:10])
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_clear:"))
async def cb_admin_user_clear(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    ok, total = await clear_user_messages(uid)
    if not ok:
        await call.answer("Xato", show_alert=True)
        return
    await call.message.answer(f"🗑 Tozalandi: {total} ta")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_req:"))
async def cb_admin_user_req(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    uid = int(call.data.split(":", 1)[1])
    report = await debug_required_for_user(uid)
    if not report:
        await call.message.answer("Aktiv required yo'q")
        await call.answer()
        return
    lines = [f"🔍 <b>REQ CHECK</b> user_id=<code>{uid}</code>", ""]
    for chat_id, title, _link, exp, status, err in report:
        ok = status in ("member", "administrator", "creator")
        lines.append(f"{'✅ OK' if ok else '❌ NOT OK'} | {html.escape((title or '').strip() or str(chat_id))}")
        lines.append(f"Chat ID: <code>{html.escape(str(chat_id))}</code>")
        lines.append(f"Status: <b>{html.escape(status)}</b>")
        lines.append(f"Expires: {html.escape(str(exp or '-'))}")
        if err:
            lines.append(f"Error: <code>{html.escape(err[:250])}</code>")
        lines.append("")
    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.message(F.text.startswith("/block "))
async def cmd_block(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /block USER_ID [sabab]")
        return
    uid = int(parts[1])
    reason = parts[2] if len(parts) > 2 else "Admin block"
    await add_to_blacklist(uid, reason)
    await message.answer("✅ Bloklandi")


@dp.message(F.text.startswith("/unblock "))
async def cmd_unblock(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /unblock USER_ID")
        return
    await remove_from_blacklist(int(parts[1]))
    await message.answer("✅ Unblock")


@dp.message(Command("blacklist"))
async def cmd_blacklist(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    rows = await get_blacklist_rows()
    if not rows:
        await message.answer("Bo'sh")
        return
    lines = ["🔴 <b>Blacklist</b>", ""]
    for uid, reason, ts in rows:
        lines.append(f"{uid} | {html.escape(reason)} | {ts}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.startswith("/admin_msg "))
async def cmd_admin_msg(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Format: /admin_msg USER_ID XABAR")
        return
    to_id = int(parts[1])
    text = parts[2].strip()
    await save_message(message.from_user.id, to_id, f"[ADMIN] {text}")
    try:
        await bot.send_message(to_id, f"📩 <b>ADMIN XABARI</b>\n\n{html.escape(text)}", parse_mode="HTML")
        await mark_user_bot_blocked(to_id, False)
    except Exception as e:
        if is_bot_block_error(e):
            await mark_user_bot_blocked(to_id, True)
        await message.answer(f"⚠️ Yuborilmadi: {e}")
        return
    await message.answer("✅ Yuborildi")


@dp.message(F.text.startswith("/audit_user "))
async def cmd_audit_user(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /audit_user USER_ID")
        return
    uid = int(parts[1])
    sent, recv = await get_user_message_audit(uid)
    lines = [f"🔎 <b>AUDIT</b> {uid}", "", "Yuborganlari:"]
    lines += [f"➡️ {to} | {ts}\n{html.escape(msg[:140])}" for to, msg, ts in sent] or ["Yo'q"]
    lines += ["", "Olganlari:"]
    lines += [f"⬅️ {fr} | {ts}\n{html.escape(msg[:140])}" for fr, msg, ts in recv] or ["Yo'q"]
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.startswith("/announcement_history "))
async def cmd_ann_history(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /announcement_history USER_ID")
        return
    uid = int(parts[1])
    rows = await get_announcement_logs(uid)
    if not rows:
        await message.answer("Tarix yo'q")
        return
    await message.answer("\n".join([f"{ts} | {a} | {r} | {roles}" for a, r, roles, ts in rows]))


@dp.message(Command("add_char"))
async def cmd_add_char(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(CharacterAdd.name)
    await message.answer("Qahramon nomi:")


@dp.message(StateFilter(CharacterAdd.name))
async def char_name(message: types.Message, state: FSMContext):
    await state.update_data(name=(message.text or "").strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{role_emoji(r)} {r}", callback_data=f"char_add_role:{r}")] for r in ROLES])
    await state.set_state(CharacterAdd.role)
    await message.answer("Rol tanlang", reply_markup=kb)


@dp.callback_query(StateFilter(CharacterAdd.role), F.data.startswith("char_add_role:"))
async def char_role(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":", 1)[1]
    await state.update_data(role=role)
    await state.set_state(CharacterAdd.description)
    await call.message.answer("Tavsif yozing:")
    await call.answer()


@dp.message(StateFilter(CharacterAdd.description))
async def char_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text or "")
    await state.set_state(CharacterAdd.video_url)
    await message.answer("Video URL (ixtiyoriy), /skip")


@dp.message(StateFilter(CharacterAdd.video_url))
async def char_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video = "" if (message.text or "").strip() == "/skip" else (message.text or "").strip()
    await add_character(data.get("name", ""), data.get("role", "Roamer"), data.get("description", ""), video)
    await state.clear()
    await message.answer("✅ Qo'shildi")


@dp.message(Command("list_chars"))
async def cmd_list_chars(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    rows = await get_all_characters()
    if not rows:
        await message.answer("Topilmadi")
        return
    text = ["🎮 <b>Qahramonlar</b>", ""]
    for cid, name, role, _, _ in rows:
        text.append(f"{cid}. {html.escape(name)} ({role}) | /del_char {cid}")
    await message.answer("\n".join(text), parse_mode="HTML")


@dp.message(Command("del_char"))
async def cmd_del_char(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Format: /del_char CHAR_ID")
        return
    await delete_character(int(parts[1]))
    await message.answer("✅ O'chirildi")


@dp.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    if not os.path.exists(DB):
        await message.answer("DB topilmadi")
        return
    backup_file = f"mlbb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy(DB, backup_file)
    await message.answer_document(types.FSInputFile(backup_file), caption="✅ Backup")


@dp.message(F.text.startswith("/set_ad "))
async def cmd_set_ad(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 3)
    if len(parts) < 4:
        await message.answer("Format: /set_ad KUN HH.MM.SS MATN")
        return
    if not parts[1].isdigit():
        await message.answer("KUN butun son bo'lishi kerak")
        return
    days = int(parts[1])
    rep = parse_hhmmss_to_seconds(parts[2])
    if rep is None or rep <= 0:
        await message.answer("HH.MM.SS xato")
        return
    text = parts[3].strip()
    if not text:
        await message.answer("Matn bo'sh")
        return
    await set_ad_schedule(text, days, rep)
    sent = await broadcast_ad(text)
    await mark_ad_sent_now()
    await message.answer(f"✅ Reklama ishga tushdi. Darhol yuborildi: {sent}")


@dp.message(Command("show_ad"))
async def cmd_show_ad(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    cfg = await get_active_ad_config()
    if not cfg:
        await message.answer("Aktiv reklama yo'q")
        return
    r = cfg["repeat_seconds"]
    await message.answer(
        f"📢 Aktiv reklama\nMatn: {cfg['ad_text']}\nTakror: {r//3600:02d}.{(r%3600)//60:02d}.{r%60:02d}\nTugash: {cfg.get('end_at') or '-'}"
    )


@dp.message(Command("ad_on"))
async def cmd_ad_on(message: types.Message):
    if is_admin(message.from_user.id):
        await set_ad_status(True)
        await message.answer("✅ Reklama yoqildi")


@dp.message(Command("ad_off"))
async def cmd_ad_off(message: types.Message):
    if is_admin(message.from_user.id):
        await set_ad_status(False)
        await message.answer("✅ Reklama o'chirildi")


@dp.message(F.text.startswith("/req_add "))
async def cmd_req_add(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    raw = (message.text or "").replace("/req_add", "", 1).strip()
    tokens = raw.split()
    if len(tokens) < 3:
        await message.answer("Format: /req_add CHAT_ID LINK KUN [NOM]")
        return
    chat_id = tokens[0]
    rest = tokens[1:]
    invite_link, invite_idx = None, -1
    for i, t in enumerate(rest):
        if t.startswith("https://"):
            invite_link, invite_idx = t, i
            break
    if not invite_link:
        await message.answer("INVITE_LINK topilmadi")
        return
    rest2 = rest[:invite_idx] + rest[invite_idx + 1 :]
    day_idx, days = -1, None
    for i, t in enumerate(rest2):
        d = "".join(ch for ch in t if ch.isdigit())
        if d:
            day_idx = i
            days = int(d)
            break
    if not days:
        await message.answer("❌ KUN butun son bo'lishi kerak")
        return
    title_tokens = rest2[:]
    if day_idx >= 0:
        title_tokens.pop(day_idx)
    title = " ".join(title_tokens)
    ok, info = await add_required_chat(chat_id, invite_link, title, days)
    if not ok:
        await message.answer(f"❌ Xato\n{info}")
        return
    await message.answer(f"✅ Qo'shildi\nChat ID: {info}\nNom: {title or '-'}\nDavomiylik: {days} kun")


@dp.message(F.text.startswith("/req_remove "))
async def cmd_req_remove(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 1)
    if len(parts) < 2:
        await message.answer("Format: /req_remove CHAT_ID")
        return
    await remove_required_chat(parts[1].strip())
    await message.answer("✅ O'chirildi")


@dp.message(Command("req_list"))
async def cmd_req_list(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    rows = await get_required_chats(active_only=False)
    if not rows:
        await message.answer("Required chat yo'q")
        return
    lines = ["🔒 <b>Required chatlar</b>", ""]
    for chat_id, title, link, active, exp in rows:
        lines.append(
            f"ID: <code>{html.escape(str(chat_id))}</code>\nNom: {html.escape(title or '-')}\n"
            f"Link: {html.escape(link)}\nExpires: {exp or '-'}\nHolat: {'✅' if active==1 else '⛔'}\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.startswith("/req_check "))
async def cmd_req_check(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(" ", 1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.answer("Format: /req_check USER_ID")
        return
    uid = int(parts[1].strip())
    report = await debug_required_for_user(uid)
    if not report:
        await message.answer("Aktiv required yo'q")
        return
    out = [f"🔍 <b>REQ CHECK</b> user_id=<code>{uid}</code>", ""]
    for chat_id, title, _link, exp, status, err in report:
        ok = status in ("member", "administrator", "creator")
        out.append(f"{'✅ OK' if ok else '❌ NOT OK'} | {html.escape((title or '').strip() or str(chat_id))}")
        out.append(f"Chat ID: <code>{html.escape(str(chat_id))}</code>")
        out.append(f"Status: <b>{html.escape(status)}</b>")
        out.append(f"Expires: {exp or '-'}")
        if err:
            out.append(f"Error: <code>{html.escape(err[:250])}</code>")
        out.append("")
    await message.answer("\n".join(out), parse_mode="HTML")


@dp.message(Command("chat_id"))
async def cmd_chat_id(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    chat = message.chat
    title = chat.title or chat.full_name or chat.username or "Private"
    await message.answer(f"Chat ID: <code>{chat.id}</code>\nNom: {html.escape(title)}", parse_mode="HTML")


@dp.message(Command("get_chat_id"))
async def cmd_get_chat_id(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Kanal/guruhdan postni botga forward qiling. ID ni chiqaraman.")


@dp.callback_query(F.data == "check_join_status")
async def cb_check_join(call: types.CallbackQuery):
    if is_admin(call.from_user.id):
        await call.answer("Admin bypass")
        return
    missing = await get_missing_required_chats(call.from_user.id)
    if missing:
        await call.message.answer("❌ Hali hammasiga qo'shilmagansiz", reply_markup=required_join_kb(missing))
        await call.answer("Azo bo'lib qayta tekshiring", show_alert=True)
        return
    await call.message.answer("✅ Tasdiqlandi", reply_markup=main_kb())
    await call.answer("OK")


@dp.callback_query(F.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Bekor")
    await call.answer()


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor", reply_markup=main_kb())


@dp.message()
async def unknown_or_forward(message: types.Message, state: FSMContext):
    # Admin helper: forward qilingan postdan chat id ni olish.
    if is_admin(message.from_user.id):
        fchat = getattr(message, "forward_from_chat", None)
        if fchat is not None:
            title = fchat.title or fchat.full_name or fchat.username or "Unknown"
            uname = f"@{fchat.username}" if fchat.username else "-"
            await message.answer(
                f"✅ Topildi\nChat ID: <code>{fchat.id}</code>\nNom: {html.escape(title)}\nUsername: {html.escape(uname)}",
                parse_mode="HTML",
            )
            return
    cur = await state.get_state()
    if cur:
        await state.clear()
    await message.answer("❓ Tanilmadi", reply_markup=main_kb())


async def main():
    global ad_worker_task
    dp.update.outer_middleware(SecurityMiddleware())
    await init_db()
    ad_worker_task = asyncio.create_task(ad_worker_loop())
    logger.info("Database initialized")
    logger.info("BOT ISHGA TUSHDI")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if ad_worker_task:
            ad_worker_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
