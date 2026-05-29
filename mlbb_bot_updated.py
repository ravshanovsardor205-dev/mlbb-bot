"""
MLBB Duo Finder Bot - FULL PATCHED VERSION (Original style preserved)
Railway optimized + Admin Panel + User Blocking + Blacklist + Characters + MLBB Info
+ /edit_char (Qahramonni tahrirlash) qo'shilgan

Install:
pip install aiogram aiosqlite python-dotenv
"""

import asyncio
import html
import json
import logging
import os
from datetime import datetime, timedelta

import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv


# .env dan o'qish
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
DB = os.getenv("DATABASE", "mlbb.db")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7509257102"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env faylga BOT_TOKEN kiriting.")


bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
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


class CharacterAdd(StatesGroup):
    name = State()
    role = State()
    description = State()
    video_url = State()


class CharacterEdit(StatesGroup):
    name = State()
    role = State()
    description = State()
    video_url = State()


class AdminMessaging(StatesGroup):
    typing_message = State()


class DBSession:
    def __init__(self, path: str):
        self.path = path
        self.db = None

    # `async with await connect_db()` yozilgan joylarni backward-compatible ushlab turadi.
    def __await__(self):
        async def _identity():
            return self

        return _identity().__await__()

    async def __aenter__(self):
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL;")
        await self.db.execute("PRAGMA synchronous=NORMAL;")
        await self.db.execute("PRAGMA foreign_keys=ON;")
        await self.db.execute("PRAGMA busy_timeout=5000;")
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        if self.db is not None:
            await self.db.close()


def connect_db():
    return DBSession(DB)


async def init_db():
    try:
        async with await connect_db() as db:
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
                    description TEXT DEFAULT '',
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

            # Eski DB bilan moslik (mavjud jadvalga yangi ustunlar qo'shish).
            try:
                await db.execute("ALTER TABLE required_chats ADD COLUMN expires_at DATETIME")
            except Exception:
                pass
            for col_def in [
                "repeat_seconds INTEGER DEFAULT 0",
                "start_at DATETIME",
                "end_at DATETIME",
                "last_sent_at DATETIME",
            ]:
                try:
                    await db.execute(f"ALTER TABLE ad_config ADD COLUMN {col_def}")
                except Exception:
                    pass

            for col_def in [
                "last_activity DATETIME",
                "bot_blocked INTEGER DEFAULT 0",
            ]:
                try:
                    await db.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
                except Exception:
                    pass

            await db.commit()
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database error: {e}")


async def db_get(user_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT user_id, username, full_name, rank, roles, looking_for_rank, looking_for_roles FROM users WHERE user_id=?",
                (user_id,),
            )
            return await cur.fetchone()
    except Exception as e:
        logger.error(f"db_get error: {e}")
        return None


async def db_save(
    user_id: int,
    username: str,
    full_name: str,
    rank: str = None,
    roles: list = None,
    looking_for_rank: str = None,
    looking_for_roles: list = None,
):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT rank, roles, looking_for_rank, looking_for_roles FROM users WHERE user_id=?",
                (user_id,),
            )
            row = await cur.fetchone()

            new_rank = rank if rank and rank != "Unranked" else (row[0] if row else "Unranked")
            new_roles = roles if roles is not None else (json.loads(row[1]) if row and row[1] else [])
            new_looking_rank = looking_for_rank if looking_for_rank and looking_for_rank != "Unranked" else (row[2] if row else "Unranked")
            new_looking_roles = looking_for_roles if looking_for_roles is not None else (json.loads(row[3]) if row and row[3] else [])

            if row is None:
                await db.execute(
                    "INSERT INTO users (user_id, username, full_name, rank, roles, looking_for_rank, looking_for_roles) VALUES (?,?,?,?,?,?,?)",
                    (
                        user_id,
                        username,
                        full_name,
                        new_rank,
                        json.dumps(new_roles),
                        new_looking_rank,
                        json.dumps(new_looking_roles),
                    ),
                )
                await db.execute("INSERT OR IGNORE INTO user_stats (user_id) VALUES (?)", (user_id,))
            else:
                await db.execute(
                    "UPDATE users SET username=?, full_name=?, rank=?, roles=?, looking_for_rank=?, looking_for_roles=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                    (
                        username,
                        full_name,
                        new_rank,
                        json.dumps(new_roles),
                        new_looking_rank,
                        json.dumps(new_looking_roles),
                        user_id,
                    ),
                )

            await db.commit()
            return True
    except Exception as e:
        logger.error(f"db_save error: {e}")
        return False


async def mark_user_activity(user: types.User):
    try:
        async with await connect_db() as db:
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
    except Exception as e:
        logger.error(f"mark_user_activity error: {e}")


async def mark_user_bot_blocked(user_id: int, blocked: bool = True):
    try:
        async with await connect_db() as db:
            await db.execute(
                "UPDATE users SET bot_blocked=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (1 if blocked else 0, user_id),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"mark_user_bot_blocked error: {e}")


async def save_message(from_id: int, to_id: int, text: str):
    try:
        async with await connect_db() as db:
            await db.execute("INSERT INTO messages (from_id, to_id, text) VALUES (?,?,?)", (from_id, to_id, text))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"save_message error: {e}")
        return False


async def get_messages(from_id: int, to_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT msg_id, from_id, text, timestamp FROM messages WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) ORDER BY timestamp ASC",
                (from_id, to_id, to_id, from_id),
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_messages error: {e}")
        return []


async def get_contacts(user_id: int):
    try:
        async with await connect_db() as db:
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
    except Exception as e:
        logger.error(f"get_contacts error: {e}")
        return []


async def add_announcement(user_id: int, rank: str, roles: list):
    try:
        async with await connect_db() as db:
            await db.execute("DELETE FROM announcements WHERE user_id=?", (user_id,))
            await db.execute(
                "INSERT INTO announcements (user_id, rank, roles) VALUES (?,?,?)",
                (user_id, rank, json.dumps(roles)),
            )
            await db.execute(
                "INSERT INTO announcement_logs (user_id, action, rank, roles) VALUES (?, 'create', ?, ?)",
                (user_id, rank, json.dumps(roles)),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"add_announcement error: {e}")
        return False


async def get_user_announcement(user_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT announce_id, user_id, rank, roles, timestamp FROM announcements WHERE user_id=?",
                (user_id,),
            )
            return await cur.fetchone()
    except Exception as e:
        logger.error(f"get_user_announcement error: {e}")
        return None


async def delete_announcement(user_id: int):
    try:
        old = await get_user_announcement(user_id)
        async with await connect_db() as db:
            await db.execute("DELETE FROM announcements WHERE user_id=?", (user_id,))
            if old:
                await db.execute(
                    "INSERT INTO announcement_logs (user_id, action, rank, roles) VALUES (?, 'delete', ?, ?)",
                    (user_id, old[2], old[3]),
                )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"delete_announcement error: {e}")
        return False


async def get_announcements_by_rank_and_roles(rank: str, roles: list):
    try:
        async with await connect_db() as db:
            idx = RANKS.index(rank)
            nearby_ranks = [RANKS[i] for i in range(max(0, idx - 1), min(len(RANKS), idx + 2))]
            placeholders = ",".join("?" * len(nearby_ranks))
            cur = await db.execute(
                f"SELECT user_id, rank, roles FROM announcements WHERE rank IN ({placeholders}) ORDER BY timestamp DESC",
                nearby_ranks,
            )
            rows = await cur.fetchall()

        matched = []
        for user_id, ann_rank, roles_str in rows:
            try:
                ann_roles = json.loads(roles_str) if roles_str else []
            except Exception:
                ann_roles = []
            if any(role in ann_roles for role in roles):
                user_data = await db_get(user_id)
                if user_data:
                    matched.append((user_id, user_data[1], user_data[2], ann_rank, ann_roles))
        return matched
    except Exception as e:
        logger.error(f"get_announcements_by_rank_and_roles error: {e}")
        return []


async def add_to_blacklist(user_id: int, reason: str = "Noma'lum"):
    try:
        async with await connect_db() as db:
            await db.execute("INSERT OR REPLACE INTO blacklist (user_id, reason) VALUES (?,?)", (user_id, reason))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"add_to_blacklist error: {e}")
        return False


async def remove_from_blacklist(user_id: int):
    try:
        async with await connect_db() as db:
            await db.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"remove_from_blacklist error: {e}")
        return False


async def is_blacklisted(user_id: int):
    if user_id == ADMIN_ID:
        return False
    try:
        async with await connect_db() as db:
            cur = await db.execute("SELECT user_id FROM blacklist WHERE user_id=?", (user_id,))
            return await cur.fetchone() is not None
    except Exception as e:
        logger.error(f"is_blacklisted error: {e}")
        return False


async def get_blacklist():
    try:
        async with await connect_db() as db:
            cur = await db.execute("SELECT user_id, reason, timestamp FROM blacklist ORDER BY timestamp DESC")
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_blacklist error: {e}")
        return []


async def add_character(name: str, role: str, description: str, video_url: str = ""):
    try:
        async with await connect_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO characters (name, role, description, video_url) VALUES (?,?,?,?)",
                (name, role, description, video_url),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"add_character error: {e}")
        return False


async def get_character_by_id(char_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT char_id, name, role, description, video_url FROM characters WHERE char_id=?",
                (char_id,),
            )
            return await cur.fetchone()
    except Exception as e:
        logger.error(f"get_character_by_id error: {e}")
        return None


async def update_character(char_id: int, name: str, role: str, description: str, video_url: str = ""):
    try:
        async with await connect_db() as db:
            await db.execute(
                "UPDATE characters SET name=?, role=?, description=?, video_url=? WHERE char_id=?",
                (name, role, description, video_url, char_id),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"update_character error: {e}")
        return False


async def get_characters_by_role(role: str):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT char_id, name, role, description, video_url FROM characters WHERE role=? ORDER BY name ASC",
                (role,),
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_characters_by_role error: {e}")
        return []


async def get_all_characters():
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT char_id, name, role, description, video_url FROM characters ORDER BY role, name ASC"
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_all_characters error: {e}")
        return []


async def delete_character(char_id: int):
    try:
        async with await connect_db() as db:
            await db.execute("DELETE FROM characters WHERE char_id=?", (char_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"delete_character error: {e}")
        return False


async def init_user_stats(user_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute("SELECT user_id FROM user_stats WHERE user_id=?", (user_id,))
            if await cur.fetchone() is None:
                await db.execute("INSERT INTO user_stats (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return True
    except Exception as e:
        logger.error(f"init_user_stats error: {e}")
    return False


async def record_match(user_id: int, partner_id: int, result: str, duo_rank: str, duo_roles: list):
    try:
        async with await connect_db() as db:
            await db.execute(
                "INSERT INTO match_history (user_id, partner_id, result, duo_rank, duo_roles) VALUES (?,?,?,?,?)",
                (user_id, partner_id, result, duo_rank, json.dumps(duo_roles)),
            )

            cur = await db.execute("SELECT total_games, total_wins, total_losses FROM user_stats WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            if row:
                total_games = row[0] + 1
                total_wins = row[1] + (1 if result == "win" else 0)
                total_losses = row[2] + (1 if result != "win" else 0)
                win_rate = (total_wins / total_games * 100) if total_games > 0 else 0
                await db.execute(
                    "UPDATE user_stats SET total_games=?, total_wins=?, total_losses=?, win_rate=?, updated_date=CURRENT_TIMESTAMP WHERE user_id=?",
                    (total_games, total_wins, total_losses, win_rate, user_id),
                )
            await db.commit()

        await check_and_award_achievements(user_id)
        return True
    except Exception as e:
        logger.error(f"record_match error: {e}")
        return False


async def get_user_stats(user_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT total_games, total_wins, total_losses, win_rate, playtime_mins FROM user_stats WHERE user_id=?",
                (user_id,),
            )
            return await cur.fetchone()
    except Exception as e:
        logger.error(f"get_user_stats error: {e}")
        return None


async def get_match_history(user_id: int, limit: int = 10):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT match_id, partner_id, result, duo_rank, match_date FROM match_history WHERE user_id=? ORDER BY match_date DESC LIMIT ?",
                (user_id, limit),
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_match_history error: {e}")
        return []


BADGES = {
    "new_player": {"emoji": "🆕", "name": "New Player", "req": "0 games"},
    "starter": {"emoji": "🚀", "name": "Starter", "req": "10+ games"},
    "experienced": {"emoji": "⭐", "name": "Experienced", "req": "50+ games"},
    "veteran": {"emoji": "👑", "name": "Veteran", "req": "100+ games"},
    "legend": {"emoji": "🔱", "name": "Legend", "req": "250+ games"},
    "high_winrate": {"emoji": "🎯", "name": "Sharp Shooter", "req": "≥70% win rate"},
    "duo_master": {"emoji": "👥", "name": "Duo Master", "req": "50+ duo games"},
}


async def get_duo_games_count(user_id: int) -> int:
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM match_history WHERE user_id=? AND partner_id IS NOT NULL",
                (user_id,),
            )
            row = await cur.fetchone()
            return int(row[0] if row else 0)
    except Exception as e:
        logger.error(f"get_duo_games_count error: {e}")
        return 0


async def check_and_award_achievements(user_id: int):
    try:
        stats = await get_user_stats(user_id)
        if not stats:
            return []

        total_games, _, _, win_rate, _ = stats
        duo_games = await get_duo_games_count(user_id)
        awarded = []
        if total_games == 1:
            await add_achievement(user_id, "new_player", "🆕")
            awarded.append("new_player")
        if total_games >= 10:
            await add_achievement(user_id, "starter", "🚀")
            awarded.append("starter")
        if total_games >= 50:
            await add_achievement(user_id, "experienced", "⭐")
            awarded.append("experienced")
        if total_games >= 100:
            await add_achievement(user_id, "veteran", "👑")
            awarded.append("veteran")
        if total_games >= 250:
            await add_achievement(user_id, "legend", "🔱")
            awarded.append("legend")
        if total_games >= 20 and win_rate >= 70:
            await add_achievement(user_id, "high_winrate", "🎯")
            awarded.append("high_winrate")
        if duo_games >= 50:
            await add_achievement(user_id, "duo_master", "👥")
            awarded.append("duo_master")
        return awarded
    except Exception as e:
        logger.error(f"check_and_award_achievements error: {e}")
        return []


async def add_achievement(user_id: int, badge_name: str, emoji: str = "🏅"):
    try:
        async with await connect_db() as db:
            await db.execute(
                "INSERT OR IGNORE INTO achievements (user_id, badge_name, badge_emoji) VALUES (?,?,?)",
                (user_id, badge_name, emoji),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"add_achievement error: {e}")
        return False


async def get_user_achievements(user_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT badge_name, badge_emoji, earned_date FROM achievements WHERE user_id=? ORDER BY earned_date DESC",
                (user_id,),
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_user_achievements error: {e}")
        return []


async def get_leaderboard(metric: str = "total_games", limit: int = 10):
    try:
        async with await connect_db() as db:
            if metric == "total_games":
                cur = await db.execute(
                    "SELECT user_id, total_games, win_rate FROM user_stats WHERE total_games > 0 ORDER BY total_games DESC LIMIT ?",
                    (limit,),
                )
            elif metric == "win_rate":
                cur = await db.execute(
                    "SELECT user_id, total_games, win_rate FROM user_stats WHERE total_games >= 20 ORDER BY win_rate DESC LIMIT ?",
                    (limit,),
                )
            else:
                cur = await db.execute(
                    "SELECT user_id, total_games, win_rate FROM user_stats WHERE total_games > 0 ORDER BY total_games DESC LIMIT ?",
                    (limit,),
                )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_leaderboard error: {e}")
        return []


async def get_announcement_logs(user_id: int, limit: int = 20):
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT action, rank, roles, timestamp FROM announcement_logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_announcement_logs error: {e}")
        return []


async def get_user_message_audit(user_id: int, limit: int = 10):
    try:
        async with await connect_db() as db:
            sent_cur = await db.execute(
                "SELECT to_id, text, timestamp FROM messages WHERE from_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            )
            recv_cur = await db.execute(
                "SELECT from_id, text, timestamp FROM messages WHERE to_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            )
            sent = await sent_cur.fetchall()
            recv = await recv_cur.fetchall()
            return sent, recv
    except Exception as e:
        logger.error(f"get_user_message_audit error: {e}")
        return [], []


async def clear_user_messages(user_id: int):
    try:
        async with await connect_db() as db:
            cur = await db.execute("SELECT COUNT(*) FROM messages WHERE from_id=? OR to_id=?", (user_id, user_id))
            row = await cur.fetchone()
            total = int(row[0] if row else 0)
            await db.execute("DELETE FROM messages WHERE from_id=? OR to_id=?", (user_id, user_id))
            await db.commit()
            return True, total
    except Exception as e:
        logger.error(f"clear_user_messages error: {e}")
        return False, 0


def _now_utc() -> datetime:
    return datetime.utcnow()


def _dt_to_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _str_to_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(value)
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
    if hh < 0 or mm < 0 or ss < 0 or mm > 59 or ss > 59:
        return None
    return hh * 3600 + mm * 60 + ss


def _is_bot_block_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return ("bot was blocked by the user" in text) or ("forbidden" in text and "bot" in text)


def explain_req_error(error_text: str) -> str:
    t = (error_text or "").lower()
    if "chat not found" in t:
        return "Chat topilmadi: CHAT_ID noto'g'ri yoki bot bu chatda yo'q."
    if "user not found" in t:
        return "User chatda topilmadi yoki join request hali tasdiqlanmagan."
    if "forbidden" in t:
        return "Botda yetarli huquq yo'q. Botni chatga qo'shib admin qiling."
    if "need administrator rights" in t:
        return "Bot admin huquqiga ega bo'lishi kerak."
    return "Noma'lum xato. /req_remove va /req_add bilan qayta sozlang."


async def get_required_chats(active_only: bool = True):
    try:
        await cleanup_expired_required_chats()
        async with await connect_db() as db:
            if active_only:
                cur = await db.execute(
                    "SELECT chat_id, title, invite_link, expires_at FROM required_chats "
                    "WHERE is_active=1 AND (expires_at IS NULL OR datetime(expires_at) > datetime('now')) "
                    "ORDER BY req_id ASC"
                )
            else:
                cur = await db.execute(
                    "SELECT chat_id, title, invite_link, is_active, expires_at FROM required_chats ORDER BY req_id ASC"
                )
            return await cur.fetchall()
    except Exception as e:
        logger.error(f"get_required_chats error: {e}")
        return []


async def add_required_chat(chat_id: str, invite_link: str, title: str = "", duration_days: int = 1):
    try:
        normalized_chat_id = await resolve_chat_id(chat_id, invite_link)
        if not normalized_chat_id:
            return False, "CHAT_ID yoki link noto'g'ri. /chat_id yoki /get_chat_id bilan qayta tekshiring."

        expires_at = _dt_to_str(_now_utc() + timedelta(days=max(1, duration_days)))
        async with await connect_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO required_chats (chat_id, title, invite_link, is_active, expires_at) "
                "VALUES (?, ?, ?, 1, ?)",
                (normalized_chat_id, title, invite_link, expires_at),
            )
            await db.commit()
            return True, normalized_chat_id
    except Exception as e:
        logger.error(f"add_required_chat error: {e}")
        return False, str(e)


async def cleanup_expired_required_chats():
    try:
        async with await connect_db() as db:
            await db.execute(
                "DELETE FROM required_chats WHERE expires_at IS NOT NULL AND datetime(expires_at) <= datetime('now')"
            )
            await db.commit()
    except Exception as e:
        logger.error(f"cleanup_expired_required_chats error: {e}")


async def remove_required_chat(chat_id: str):
    try:
        async with await connect_db() as db:
            await db.execute("DELETE FROM required_chats WHERE chat_id=?", (chat_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"remove_required_chat error: {e}")
        return False


async def get_active_ad_text():
    cfg = await get_active_ad_config()
    return cfg["ad_text"] if cfg else None


async def get_active_ad_config():
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT ad_text, is_active, repeat_seconds, start_at, end_at, last_sent_at "
                "FROM ad_config WHERE config_id=1"
            )
            row = await cur.fetchone()
            if not row:
                return None
            ad_text, is_active, repeat_seconds, start_at, end_at, last_sent_at = row
            if is_active != 1 or not (ad_text or "").strip():
                return None

            end_dt = _str_to_dt(end_at)
            if end_dt and _now_utc() >= end_dt:
                await clear_ad_config()
                return None

            return {
                "ad_text": ad_text.strip(),
                "repeat_seconds": int(repeat_seconds or 0),
                "start_at": start_at,
                "end_at": end_at,
                "last_sent_at": last_sent_at,
            }
    except Exception as e:
        logger.error(f"get_active_ad_config error: {e}")
        return None


async def set_ad_text(ad_text: str):
    try:
        async with await connect_db() as db:
            await db.execute(
                "UPDATE ad_config SET ad_text=?, updated_at=CURRENT_TIMESTAMP WHERE config_id=1",
                (ad_text,),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"set_ad_text error: {e}")
        return False


async def set_ad_schedule(ad_text: str, duration_days: int, repeat_seconds: int):
    try:
        now = _now_utc()
        end_at = now + timedelta(days=max(1, duration_days))
        async with await connect_db() as db:
            await db.execute(
                """
                UPDATE ad_config
                SET ad_text=?, is_active=1, repeat_seconds=?, start_at=?, end_at=?, last_sent_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE config_id=1
                """,
                (ad_text.strip(), int(repeat_seconds), _dt_to_str(now), _dt_to_str(end_at)),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"set_ad_schedule error: {e}")
        return False


async def set_ad_status(is_active: bool):
    try:
        async with await connect_db() as db:
            await db.execute(
                "UPDATE ad_config SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE config_id=1",
                (1 if is_active else 0,),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"set_ad_status error: {e}")
        return False


async def mark_ad_sent_now():
    try:
        async with await connect_db() as db:
            await db.execute(
                "UPDATE ad_config SET last_sent_at=?, updated_at=CURRENT_TIMESTAMP WHERE config_id=1",
                (_dt_to_str(_now_utc()),),
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"mark_ad_sent_now error: {e}")
        return False


async def clear_ad_config():
    try:
        async with await connect_db() as db:
            await db.execute(
                """
                UPDATE ad_config
                SET ad_text='', is_active=0, repeat_seconds=0, start_at=NULL, end_at=NULL, last_sent_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE config_id=1
                """
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"clear_ad_config error: {e}")
        return False


async def broadcast_ad_to_all(ad_text: str):
    sent = 0
    text = f"📢 <b>REKLAMA</b>\n\n{html.escape(ad_text)}"
    try:
        async with await connect_db() as db:
            cur = await db.execute("SELECT user_id FROM users ORDER BY created_at DESC")
            rows = await cur.fetchall()
        for (uid,) in rows:
            try:
                await bot.send_message(uid, text, parse_mode="HTML")
                sent += 1
                await mark_user_bot_blocked(uid, blocked=False)
            except Exception as e:
                if _is_bot_block_error(e):
                    await mark_user_bot_blocked(uid, blocked=True)
                continue
    except Exception as e:
        logger.error(f"broadcast_ad_to_all error: {e}")
    return sent


async def ad_worker_loop():
    while True:
        try:
            cfg = await get_active_ad_config()
            if cfg:
                repeat_seconds = int(cfg.get("repeat_seconds") or 0)
                if repeat_seconds > 0:
                    last_dt = _str_to_dt(cfg.get("last_sent_at"))
                    now = _now_utc()
                    if not last_dt or (now - last_dt).total_seconds() >= repeat_seconds:
                        await broadcast_ad_to_all(cfg["ad_text"])
                        await mark_ad_sent_now()
        except Exception as e:
            logger.error(f"ad_worker_loop error: {e}")
        await asyncio.sleep(2)


def _chat_id_value(chat_id: str):
    chat_id = str(chat_id).strip()
    try:
        return int(chat_id)
    except Exception:
        return chat_id


def _username_from_invite_link(invite_link: str):
    link = (invite_link or "").strip()
    if not link:
        return None
    if "t.me/" not in link:
        return None
    tail = link.split("t.me/", 1)[1].strip().strip("/")
    if not tail or tail.startswith("+") or tail.startswith("joinchat"):
        return None
    username = tail.split("/", 1)[0].split("?", 1)[0].strip()
    if not username:
        return None
    return f"@{username}"


async def resolve_chat_id(chat_id: str, invite_link: str):
    """CHAT_ID ni tekshiradi va iloji bo'lsa to'g'ri ID ga normalizatsiya qiladi."""
    # 1) Kiritilgan chat_id bo'yicha tekshirish
    try:
        chat = await bot.get_chat(_chat_id_value(chat_id))
        return str(chat.id)
    except Exception:
        pass

    # 2) Public username link bo'lsa, @username orqali tekshirish
    username = _username_from_invite_link(invite_link)
    if username:
        try:
            chat = await bot.get_chat(username)
            return str(chat.id)
        except Exception:
            return None

    # 3) Private invite link (+...) bilan resolve qilib bo'lmaydi
    return None


async def get_missing_required_chats(user_id: int):
    required = await get_required_chats(active_only=True)
    missing = []
    for chat_id, title, invite_link, _expires_at in required:
        try:
            member = await bot.get_chat_member(chat_id=_chat_id_value(chat_id), user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                missing.append((chat_id, title, invite_link))
        except Exception:
            missing.append((chat_id, title, invite_link))
    return missing


async def debug_required_chats_for_user(user_id: int):
    """Admin debug: required chatlar bo'yicha membership holatini batafsil qaytaradi."""
    result = []
    required = await get_required_chats(active_only=True)
    for chat_id, title, invite_link, expires_at in required:
        label = (title or "").strip() or str(chat_id)
        try:
            member = await bot.get_chat_member(chat_id=_chat_id_value(chat_id), user_id=user_id)
            status = member.status
            ok = status in ("member", "administrator", "creator")
            result.append(
                {
                    "chat_id": str(chat_id),
                    "title": label,
                    "invite_link": invite_link,
                    "expires_at": expires_at,
                    "ok": ok,
                    "status": status,
                    "error": "",
                }
            )
        except Exception as e:
            result.append(
                {
                    "chat_id": str(chat_id),
                    "title": label,
                    "invite_link": invite_link,
                    "expires_at": expires_at,
                    "ok": False,
                    "status": "unknown",
                    "error": str(e),
                }
            )
    return result


def is_profile_complete(rank: str, roles_str) -> bool:
    try:
        if rank in (None, "Unranked", ""):
            return False
        if isinstance(roles_str, str):
            roles_list = json.loads(roles_str) if roles_str and roles_str != "[]" else []
        else:
            roles_list = roles_str if roles_str else []
        return len(roles_list) > 0
    except Exception:
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
            return "Tanlanmagan"
        return "  ".join([f"{ro(r)} {r}" for r in roles_list])
    except Exception:
        return "Xato"


def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Profil"), KeyboardButton(text="🔍 Sherik topish")],
            [KeyboardButton(text="📢 E'lon berish"), KeyboardButton(text="💬 Xabarlar")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📚 MLBB haqida")],
            [KeyboardButton(text="❓ Yordam"), KeyboardButton(text="📞 Admin bilan bog'lanish")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Buyruq tanlang...",
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
        row.append(InlineKeyboardButton(text=f"☐ {ro(r)} {r}", callback_data=f"{prefix}:{r}"))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data=f"{prefix}:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profile_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Rank", callback_data="edit_rank"),
                InlineKeyboardButton(text="✏️ Rollar", callback_data="edit_roles"),
            ],
            [
                InlineKeyboardButton(text="🎮 Dost topish", callback_data="find_duo"),
                InlineKeyboardButton(text="📢 E'lon berish", callback_data="announce_duo"),
            ],
        ]
    )


def announce_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, e'lon ber", callback_data="confirm_announce"),
                InlineKeyboardButton(text="❌ Bekor", callback_data="cancel"),
            ]
        ]
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
    rows = []
    for role in ROLES:
        rows.append([InlineKeyboardButton(text=f"{ro(role)} {role}", callback_data=f"char_role:{role}")])
    rows.append([InlineKeyboardButton(text="❌ Orqaga", callback_data="mlbb_info")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_actions_kb(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Xabar yozish", callback_data=f"admin_user_msg:{user_id}"),
                InlineKeyboardButton(text="🔴 Blok qilish", callback_data=f"admin_user_block:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="📝 Chat tarixi", callback_data=f"admin_user_chat:{user_id}"),
                InlineKeyboardButton(text="📢 E'lon tarixi", callback_data=f"admin_user_ann:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="🟢 Unblock", callback_data=f"admin_user_unblock:{user_id}"),
                InlineKeyboardButton(text="📊 Stat", callback_data=f"admin_user_stat:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="🔍 Req Check", callback_data=f"admin_user_req:{user_id}"),
            ],
            [
                InlineKeyboardButton(text="🗑 Xabarlarni tozalash", callback_data=f"admin_user_clear:{user_id}"),
            ],
        ]
    )


def required_join_kb(missing_chats):
    rows = []
    for chat_id, title, invite_link in missing_chats:
        label = title.strip() if (title or "").strip() else f"Chat {chat_id}"
        rows.append([InlineKeyboardButton(text=f"➕ {label}", url=invite_link)])
    rows.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_join_status")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


class BlacklistMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user") or getattr(event, "from_user", None)

        if user is None and isinstance(event, types.Update):
            if event.message and event.message.from_user:
                user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                user = event.callback_query.from_user
            elif event.inline_query and event.inline_query.from_user:
                user = event.inline_query.from_user

        if user:
            await mark_user_activity(user)

        if user and user.id != ADMIN_ID and await is_blacklisted(user.id):
            try:
                callback = event if isinstance(event, types.CallbackQuery) else None
                message = event if isinstance(event, types.Message) else None

                if isinstance(event, types.Update):
                    callback = event.callback_query
                    message = event.message

                if callback:
                    await callback.answer("Siz bloklangansiz", show_alert=True)
                elif message:
                    await message.answer("🔴 Siz bloklangansiz! Botdan foydalana olmaysiz.")
            except Exception:
                pass
            return

        # Majburiy obuna: required channel/grouplarga azo bo'lmaguncha bot ishlamaydi.
        if user and user.id != ADMIN_ID:
            callback = event if isinstance(event, types.CallbackQuery) else None
            message = event if isinstance(event, types.Message) else None

            if isinstance(event, types.Update):
                callback = event.callback_query
                message = event.message

            callback_data = callback.data if callback else None
            if callback_data != "check_join_status":
                missing = await get_missing_required_chats(user.id)
                if missing:
                    kb = required_join_kb(missing)
                    text = (
                        "🔒 <b>Botdan foydalanish uchun avval quyidagi kanal/guruhlarga qo'shiling.</b>\n\n"
                        "Qo'shilgandan keyin <b>Tekshirish</b> tugmasini bosing.\n\n"
                        "Agar noto'g'ri tekshirsa: bot required chatlarda admin ekanini tekshiring."
                    )
                    try:
                        if callback:
                            await callback.answer("Avval required chatlarga qo'shiling", show_alert=True)
                            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
                        elif message:
                            await message.answer(text, parse_mode="HTML", reply_markup=kb)
                    except Exception:
                        pass
                    return
        return await handler(event, data)


async def send_profile(target: types.Message, user_id: int):
    u = await db_get(user_id)
    if not u:
        await target.answer("❌ Profil topilmadi. /start bilan boshlang.", reply_markup=main_kb())
        return

    _, uname, fname, rank, roles, _, looking_for_roles = u
    is_complete = is_profile_complete(rank, roles)
    login = f"@{uname}" if uname else fname or "-"
    announcement = await get_user_announcement(user_id)
    announce_status = "✅ E'lon berilgan" if announcement else "❌ E'lon berilmagan"

    msg = (
        "👤 <b>PROFILINGIZ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔹 Ism:   {html.escape(fname or '-') }\n"
        f"🔹 Login: {html.escape(login)}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🎮 SIZNING MA'LUMOTLARINGIZ</b>\n"
        f"{re(rank)} Rank: <b>{rank}</b>\n"
        f"Rollar: {format_roles(roles)}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>📢 E'LON</b>\n"
        f"{announce_status}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Qidirayotgan rollar: {format_roles(looking_for_roles)}\n"
        f"{'✅ <b>To\'liq</b>' if is_complete else '⚠️ <b>To\'liq emas</b>'}"
    )

    kb = profile_kb()
    if announcement:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Rank", callback_data="edit_rank"),
                    InlineKeyboardButton(text="✏️ Rollar", callback_data="edit_roles"),
                ],
                [
                    InlineKeyboardButton(text="🎮 Dost topish", callback_data="find_duo"),
                    InlineKeyboardButton(text="📢 E'lon berish", callback_data="announce_duo"),
                ],
                [InlineKeyboardButton(text="❌ E'lonni o'chirish", callback_data="delete_announce")],
            ]
        )

    await target.answer(msg, parse_mode="HTML", reply_markup=kb)


# USER stats command (/stats admin bilan to'qnashmasin deb /mystats)
@dp.message(Command("mystats"))
@dp.message(F.text == "📊 Statistika")
async def cmd_stats_user(message: types.Message):
    user_id = message.from_user.id
    await init_user_stats(user_id)
    stats = await get_user_stats(user_id)
    if not stats:
        await message.answer("❌ Statistika topilmadi")
        return

    total_games, total_wins, total_losses, win_rate, playtime = stats
    text = (
        "📊 <b>SIZNING STATISTIKANGIZ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 O'yinlar: <b>{total_games}</b>\n"
        f"✅ G'alaba: <b>{total_wins}</b>\n"
        f"❌ Mag'lubiyat: <b>{total_losses}</b>\n"
        f"🎯 Win Rate: <b>{win_rate:.1f}%</b>\n"
        f"⏱️ Vaqt (min): <b>{playtime}</b>\n"
    )
    ach = await get_user_achievements(user_id)
    if ach:
        text += "\n<b>🎖️ Badges:</b>\n"
        for badge_name, emoji, _ in ach:
            text += f"{emoji} {badge_name}\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="view_leaderboard")],
            [InlineKeyboardButton(text="❌ Orqaga", callback_data="cancel")],
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "view_leaderboard")
async def cb_view_leaderboard(call: types.CallbackQuery):
    lb = await get_leaderboard("total_games", 10)
    if not lb:
        await call.answer("❌ Leaderboard bo'sh", show_alert=True)
        return
    text = "<b>🏆 TOP 10 O'YINCHILAR</b>\n\n"
    for pos, (user_id, games, win_rate) in enumerate(lb, 1):
        user = await db_get(user_id)
        user_name = user[2] if user else f"User {user_id}"
        text += f"{pos}. {html.escape(user_name)}\n   🎮 {games} o'yin ({win_rate:.1f}%)\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Orqaga", callback_data="cancel")]])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    uname = message.from_user.username or ""
    fname = message.from_user.full_name or ""
    await db_save(message.from_user.id, uname, fname)
    await init_user_stats(message.from_user.id)
    user = await db_get(message.from_user.id)
    is_complete = user and is_profile_complete(user[3], user[4])
    await message.answer(
        f"👋 Salom, <b>{html.escape(fname or uname or 'Foydalanuvchi')}</b>!\n\nMLBB Duo Finder botga xush kelibsiz!",
        parse_mode="HTML",
        reply_markup=main_kb(),
    )
    ad_text = await get_active_ad_text()
    if ad_text:
        await message.answer(f"📢 <b>REKLAMA</b>\n\n{html.escape(ad_text)}", parse_mode="HTML")
    if not is_complete:
        await message.answer("📋 Profilingizni to'ldiring. Avval rank tanlang:", reply_markup=rank_kb())
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
        await call.answer("❌ Noto'g'ri", show_alert=True)
        return
    await state.update_data(setup_rank=rank)
    await call.message.edit_text(
        f"✅ Rank: <b>{re(rank)} {rank}</b>\n\n2️⃣ Rollarni tanlang:",
        parse_mode="HTML",
        reply_markup=roles_kb("setup_role"),
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
            await call.answer("❌ Kamida 1ta rol tanlang", show_alert=True)
            return
        success = await db_save(
            call.from_user.id,
            call.from_user.username or "",
            call.from_user.full_name or "",
            rank=setup_rank,
            roles=selected_roles,
        )
        if not success:
            await call.answer("❌ Saqlash xatosi", show_alert=True)
            return
        await call.message.edit_text(
            f"✅ Saqlandi\n{re(setup_rank)} {setup_rank}\nRollar: {format_roles(selected_roles)}",
            parse_mode="HTML",
        )
        await state.clear()
        await send_profile(call.message, call.from_user.id)
        await call.answer()
        return

    if role not in ROLES:
        await call.answer("❌ Noto'g'ri", show_alert=True)
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
        row.append(InlineKeyboardButton(text=f"{checked} {ro(r)} {r}", callback_data=f"setup_role:{r}"))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="setup_role:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@dp.callback_query(F.data == "edit_roles")
async def cb_edit_roles(call: types.CallbackQuery, state: FSMContext):
    u = await db_get(call.from_user.id)
    if not u:
        await call.answer("❌ Profil topilmadi", show_alert=True)
        return
    current_roles = json.loads(u[4]) if u[4] else []
    await state.update_data(setup_roles=current_roles, setup_rank=u[3])
    await state.set_state(Setup.roles)
    await call.message.answer("🎮 Rollarni o'zgartiring:", reply_markup=roles_kb("setup_role"))
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
        await target.answer("❌ Profil topilmadi")
        return
    if not is_profile_complete(u[3], u[4]):
        await target.answer("⚠️ Profil to'liq emas. Avval rank va rol tanlang.", parse_mode="HTML")
        return
    await target.answer("🔍 Sherik qidirish\nKerakli rankni tanlang:", reply_markup=rank_kb())
    await state.set_state(Setup.finding_rank)


@dp.callback_query(StateFilter(Setup.finding_rank), F.data.startswith("rank:"))
async def cb_finding_rank(call: types.CallbackQuery, state: FSMContext):
    rank = call.data.split(":", 1)[1]
    if rank not in RANKS:
        await call.answer("❌ Noto'g'ri", show_alert=True)
        return
    await state.update_data(finding_rank=rank)
    await call.message.edit_text(
        f"✅ Rank: <b>{re(rank)} {rank}</b>\n\n2️⃣ Kerakli rollarni tanlang:",
        parse_mode="HTML",
        reply_markup=roles_kb("finding_role"),
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
            await call.answer("❌ Kamida 1ta rol tanlang", show_alert=True)
            return
        matched = await get_announcements_by_rank_and_roles(finding_rank, finding_roles)
        if not matched:
            await call.message.edit_text("😔 Sherik topilmadi")
            await state.clear()
            return
        await call.message.edit_text(
            f"✅ Topildi: <b>{len(matched)}</b> ta\n🎮 Rollar: {format_roles(finding_roles)}",
            parse_mode="HTML",
        )
        for idx, (uid, uname, fname, urank, user_roles) in enumerate(matched, 1):
            login = f"@{uname}" if uname else fname or "NoName"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💬 Xabar yuborish", callback_data=f"send_msg:{uid}")]]
            )
            text = (
                f"<b>#{idx}. {html.escape(fname or login)}</b>\n"
                f"🔑 {html.escape(login)}\n\n"
                f"{re(urank)} <b>Rank:</b> {urank}\n"
                f"🎮 <b>Rollar:</b> {format_roles(user_roles)}"
            )
            await bot.send_message(call.from_user.id, text, parse_mode="HTML", reply_markup=kb)
        await state.clear()
        return

    if role not in ROLES:
        await call.answer("❌ Noto'g'ri", show_alert=True)
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
        row.append(InlineKeyboardButton(text=f"{checked} {ro(r)} {r}", callback_data=f"finding_role:{r}"))
        if i % 2 == 1 or i == len(ROLES) - 1:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Qidirni boshlash", callback_data="finding_role:done")])
    rows.append([InlineKeyboardButton(text="❌ Bekor", callback_data="cancel")])
    await call.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@dp.callback_query(F.data.startswith("send_msg:"))
async def cb_send_msg(call: types.CallbackQuery, state: FSMContext):
    try:
        to_id = int(call.data.split(":")[1])
    except Exception:
        await call.answer("❌ Xato", show_alert=True)
        return
    to_user = await db_get(to_id)
    if not to_user:
        await call.answer("❌ Foydalanuvchi topilmadi", show_alert=True)
        return
    to_name = to_user[2] or (f"@{to_user[1]}" if to_user[1] else "Foydalanuvchi")
    await state.update_data(msg_to_id=to_id, msg_to_name=to_name)
    await state.set_state(Messaging.typing_message)
    await call.message.answer(f"💬 <b>{html.escape(to_name)}</b> ga xabar yozing:\n\nYoki /cancel", parse_mode="HTML")
    await call.answer()


@dp.message(StateFilter(Messaging.typing_message))
async def msg_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    to_id = data.get("msg_to_id")
    to_name = data.get("msg_to_name")
    if not to_id:
        await message.answer("❌ Xato")
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Bo'sh xabar yuborilmaydi")
        return
    success = await save_message(message.from_user.id, to_id, text)
    if not success:
        await message.answer("❌ Yuborilmadi")
        return
    await message.answer(f"✅ <b>{html.escape(to_name or 'Foydalanuvchi')}</b> ga yuborildi", parse_mode="HTML", reply_markup=main_kb())
    from_name = message.from_user.full_name or (f"@{message.from_user.username}" if message.from_user.username else "Foydalanuvchi")
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Javob", callback_data=f"send_msg:{message.from_user.id}")]])
        await bot.send_message(
            to_id,
            f"💬 <b>YANGI XABAR!</b>\n\nYuboruvchi: {html.escape(from_name)}\nXabar: <i>{html.escape(text)}</i>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await mark_user_bot_blocked(to_id, blocked=False)
    except Exception as e:
        logger.error(f"Notification error: {e}")
        if _is_bot_block_error(e):
            await mark_user_bot_blocked(to_id, blocked=True)
    await state.clear()


@dp.message(F.text == "💬 Xabarlar")
async def cmd_messages(message: types.Message, state: FSMContext):
    await state.clear()
    contacts = await get_contacts(message.from_user.id)
    if not contacts:
        await message.answer("📭 Kontakt yo'q", reply_markup=main_kb())
        return
    await message.answer("💬 <b>KONTAKTLAR:</b>", parse_mode="HTML")
    for contact_id, _ in contacts:
        contact = await db_get(contact_id)
        if not contact:
            continue
        _, uname, fname, rank, roles = contact[:5]
        contact_name = fname or (f"@{uname}" if uname else "Foydalanuvchi")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💬 Chat", callback_data=f"view_chat:{contact_id}"),
                    InlineKeyboardButton(text="📝 Xabar", callback_data=f"send_msg:{contact_id}"),
                ]
            ]
        )
        await message.answer(
            f"👤 <b>{html.escape(contact_name)}</b>\n{re(rank)} {rank}  🎮 {format_roles(roles)}",
            parse_mode="HTML",
            reply_markup=kb,
        )


@dp.callback_query(F.data.startswith("view_chat:"))
async def cb_view_chat(call: types.CallbackQuery):
    contact_id = int(call.data.split(":")[1])
    messages = await get_messages(call.from_user.id, contact_id)
    contact = await db_get(contact_id)
    if not contact:
        await call.answer("❌ Topilmadi", show_alert=True)
        return
    contact_name = contact[2] or (f"@{contact[1]}" if contact[1] else "Foydalanuvchi")
    if not messages:
        await call.answer(f"📭 {contact_name} bilan xabar yo'q", show_alert=True)
        return
    msg_text = f"💬 <b>{html.escape(contact_name)}</b> SUHBAT:\n━━━━━━━━━━━━━━━━━━\n\n"
    for _, from_id, text, _ in messages:
        sender = "👤 Siz" if from_id == call.from_user.id else f"👥 {html.escape(contact_name)}"
        msg_text += f"{sender}: {html.escape(text)}\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📝 Javob", callback_data=f"send_msg:{contact_id}")]])
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
        await target.answer("⚠️ Profilingiz to'liq bo'lishi kerak", reply_markup=main_kb())
        return
    _, uname, fname, rank, roles = u[:5]
    login = f"@{uname}" if uname else fname or "NoName"
    await target.answer(
        f"📢 <b>E'LON BERISH?</b>\n\n👤 {html.escape(fname or login)}\n{re(rank)} {rank}\n🎮 {format_roles(roles)}",
        parse_mode="HTML",
        reply_markup=announce_kb(),
    )


@dp.callback_query(F.data == "confirm_announce")
async def cb_announce_ok(call: types.CallbackQuery):
    u = await db_get(call.from_user.id)
    if not u:
        await call.answer("❌ Topilmadi", show_alert=True)
        return
    _, _, _, rank, roles = u[:5]
    roles_list = json.loads(roles) if roles else []
    if not await add_announcement(call.from_user.id, rank, roles_list):
        await call.answer("❌ Xato", show_alert=True)
        return
    await call.message.edit_text("✅ E'LON BERILDI")
    await call.answer("✅ OK")
    await send_profile(call.message, call.from_user.id)


@dp.callback_query(F.data == "delete_announce")
async def cb_delete_announce(call: types.CallbackQuery):
    if not await delete_announcement(call.from_user.id):
        await call.answer("❌ Xato", show_alert=True)
        return
    await call.message.edit_text("❌ E'LON O'CHIRILDI")
    await call.answer("✅ O'chirildi")
    await send_profile(call.message, call.from_user.id)


@dp.callback_query(F.data == "mlbb_info")
async def cb_mlbb_info(call: types.CallbackQuery):
    await call.message.edit_text(
        "📚 <b>MLBB HAQIDA</b>\n\nMobile Legends: Bang Bang - populyar mobil o'yin.",
        parse_mode="HTML",
        reply_markup=mlbb_info_kb(),
    )
    await call.answer()


@dp.message(F.text == "📚 MLBB haqida")
async def cmd_mlbb_info_from_menu(message: types.Message):
    await message.answer(
        "📚 <b>MLBB HAQIDA</b>\n\nMobile Legends: Bang Bang - populyar mobil o'yin.",
        parse_mode="HTML",
        reply_markup=mlbb_info_kb(),
    )


@dp.callback_query(F.data == "show_characters")
async def cb_show_characters(call: types.CallbackQuery):
    await call.message.edit_text(
        "🎮 <b>QAHRAMONLAR</b>\n\nRolni tanlang:",
        parse_mode="HTML",
        reply_markup=characters_roles_kb(),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("char_role:"))
async def cb_char_role(call: types.CallbackQuery):
    role = call.data.split(":")[1]
    characters = await get_characters_by_role(role)
    if not characters:
        await call.message.edit_text(
            f"❌ <b>{role}</b> rolida qahramon topilmadi",
            parse_mode="HTML",
            reply_markup=characters_roles_kb(),
        )
        await call.answer()
        return
    rows = [[InlineKeyboardButton(text=f"👤 {name}", callback_data=f"char_detail:{char_id}")] for char_id, name, _, _, _ in characters]
    rows.append([InlineKeyboardButton(text="❌ Orqaga", callback_data="show_characters")])
    await call.message.edit_text(
        f"🎮 <b>{role}</b> ROLIDA QAHRAMONLAR:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("char_detail:"))
async def cb_char_detail(call: types.CallbackQuery):
    char_id = int(call.data.split(":")[1])
    character = None
    for c in await get_all_characters():
        if c[0] == char_id:
            character = c
            break
    if not character:
        await call.answer("❌ Qahramon topilmadi", show_alert=True)
        return
    _, name, role, description, video_url = character
    text = f"👤 <b>{html.escape(name)}</b>\n🎮 Rol: {role}\n\n📝 <b>Tavsif:</b>\n{html.escape(description)}"
    rows = []
    if video_url:
        rows.append([InlineKeyboardButton(text="🎥 Video", url=video_url)])
    rows.append([InlineKeyboardButton(text="❌ Orqaga", callback_data=f"char_role:{role}")])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@dp.callback_query(F.data == "show_mlbb_info")
async def cb_show_mlbb_info(call: types.CallbackQuery):
    info = (
        "📖 <b>MOBILE LEGENDS: BANG BANG HAQIDA</b>\n\n"
        "<b>🎮 O'yin haqida:</b> MLBB - 5v5 MOBA o'yini.\n\n"
        "<b>🏆 Ranklar:</b> Warrior -> Elite -> Master -> Grandmaster -> Epic -> Legend -> Mythic -> Mythical Glory\n\n"
        "<b>🎯 Rollar:</b> Roamer, Gold Lane, Exp Lane, Mid Lane, Jungler"
    )
    await call.message.edit_text(
        info,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Orqaga", callback_data="mlbb_info")]]),
    )
    await call.answer()


@dp.message(Command("help"))
@dp.message(F.text == "❓ Yordam")
async def cmd_help(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📖 <b>QO'LLANMA</b>\n\n"
        "👤 Profil — Rank + rollar\n"
        "🔍 Sherik topish — E'lon bergan sheriklar\n"
        "📢 E'lon berish — Sherik izlatish\n"
        "💬 Xabarlar — Chat va kontaktlar",
        parse_mode="HTML",
        reply_markup=main_kb(),
    )


@dp.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin(message: types.Message):
    await message.answer("👨‍💻 Admin: @rSx_ravshanoff")


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    await message.answer(
        "🔧 <b>ADMIN PANEL</b>\n\n"
        "/stats - Statistika\n"
        "/users - Foydalanuvchilar\n"
        "/blacklist - Qora ro'yxat\n"
        "/backup - Backup\n"
        "/add_char - Qahramon qo'shish\n"
        "/edit_char 123 - Qahramonni tahrirlash\n"
        "/del_char - Qahramon o'chirish\n"
        "/list_chars - Qahramonlar ro'yxati\n"
        "/block 123456 sabab - Bloklash\n"
        "/unblock 123456 - Unblock\n\n"
        "<b>REKLAMA</b>\n"
        "/set_ad KUN HH.MM.SS MATN - Reklama yaratish va darhol e'lon qilish\n"
        "/show_ad - Joriy reklamani ko'rish\n"
        "/ad_on - Reklamani yoqish\n"
        "/ad_off - Reklamani o'chirish\n\n"
        "<b>MAJBURIY OBUNA</b>\n"
        "/req_add CHAT_ID LINK KUN [NOM] - Required chat qo'shish\n"
        "/req_remove CHAT_ID - Required chatni o'chirish\n"
        "/req_list - Required chatlar ro'yxati\n"
        "/get_chat_id - Forward qilingan postdan chat_id olish\n"
        "/chat_id - Joriy chatning ID sini ko'rsatish\n"
        "/req_check USER_ID - Userning required chat holatini tekshirish\n\n"
        "<b>YANGI FUNKSIYALAR</b>\n"
        "/audit_user 123456 - User xabar audit\n"
        "/announcement_history 123456 - User e'lon tarixi\n"
        "/admin_msg 123456 Salom - Userga admin xabari",
        parse_mode="HTML",
    )


@dp.message(Command("chat_id"))
async def cmd_chat_id(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    chat = message.chat
    chat_title = chat.title or chat.full_name or chat.username or "Private"
    await message.answer(
        f"🆔 Joriy chat ID: <code>{chat.id}</code>\n"
        f"Nom: {html.escape(chat_title)}",
        parse_mode="HTML",
    )


@dp.message(Command("get_chat_id"))
async def cmd_get_chat_id(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    await message.answer(
        "📌 Kanal/guruhdan bitta postni botga <b>forward</b> qiling.\n"
        "Bot sizga chat ID ni chiqarib beradi.",
        parse_mode="HTML",
    )


@dp.message(F.forward_from_chat)
async def admin_forward_chat_id_helper(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    chat_obj = getattr(message, "forward_from_chat", None)
    if chat_obj is None:
        return

    title = chat_obj.title or chat_obj.full_name or chat_obj.username or "Unknown"
    username = f"@{chat_obj.username}" if getattr(chat_obj, "username", None) else "-"
    await message.answer(
        f"✅ Topildi\n"
        f"Chat ID: <code>{chat_obj.id}</code>\n"
        f"Nom: {html.escape(title)}\n"
        f"Username: {html.escape(username)}\n\n"
        f"Misol:\n"
        f"<code>/req_add {chat_obj.id} https://t.me/your_link 30 {html.escape(title)}</code>",
        parse_mode="HTML",
    )


# ADMIN stats - /stats admin uchun saqlandi
@dp.message(Command("stats"))
async def cmd_admin_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        # /stats non-admin uchun user statistikaga fallback bo'ladi.
        await cmd_stats_user(message)
        return
    try:
        async with await connect_db() as db:
            users = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
            messages = await (await db.execute("SELECT COUNT(*) FROM messages")).fetchone()
            announcements = await (await db.execute("SELECT COUNT(*) FROM announcements")).fetchone()
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
        return
    await message.answer(
        f"📊 STATISTIKA\n\n👥 Foydalanuvchilar: {users[0]}\n💬 Xabarlar: {messages[0]}\n📢 E'lonlar: {announcements[0]}"
    )


@dp.message(F.text.startswith("/set_ad "))
async def cmd_set_ad(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    parts = message.text.split(" ", 3)
    if len(parts) < 4:
        await message.answer("❌ Format: /set_ad KUN HH.MM.SS MATN")
        return
    try:
        duration_days = int(parts[1])
    except Exception:
        await message.answer("❌ KUN butun son bo'lishi kerak")
        return
    if duration_days <= 0:
        await message.answer("❌ KUN 1 yoki undan katta bo'lsin")
        return
    repeat_seconds = parse_hhmmss_to_seconds(parts[2])
    if repeat_seconds is None or repeat_seconds <= 0:
        await message.answer("❌ HH.MM.SS format xato. Masalan: 00.30.00")
        return
    ad_text = parts[3].strip()
    if not ad_text:
        await message.answer("❌ Reklama matni bo'sh")
        return

    ok = await set_ad_schedule(ad_text, duration_days, repeat_seconds)
    if not ok:
        await message.answer("❌ Reklama saqlashda xato")
        return

    sent = await broadcast_ad_to_all(ad_text)
    await mark_ad_sent_now()
    await message.answer(
        f"✅ Reklama ishga tushdi\n"
        f"🔁 Takrorlanish: {parts[2]}\n"
        f"📆 Davomiylik: {duration_days} kun\n"
        f"📨 Hozir yuborildi: {sent} user"
    )


@dp.message(Command("show_ad"))
async def cmd_show_ad(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    cfg = await get_active_ad_config()
    if not cfg:
        await message.answer("ℹ️ Aktiv reklama yo'q")
        return
    end_at = cfg.get("end_at") or "-"
    repeat_seconds = int(cfg.get("repeat_seconds") or 0)
    hh = repeat_seconds // 3600
    mm = (repeat_seconds % 3600) // 60
    ss = repeat_seconds % 60
    await message.answer(
        "📢 <b>Aktiv reklama</b>\n\n"
        f"Matn: {html.escape(cfg['ad_text'])}\n"
        f"Takrorlanish: {hh:02d}.{mm:02d}.{ss:02d}\n"
        f"Tugash vaqti (UTC): {end_at}",
        parse_mode="HTML",
    )


@dp.message(Command("ad_on"))
async def cmd_ad_on(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    if await set_ad_status(True):
        await message.answer("✅ Reklama yoqildi")
    else:
        await message.answer("❌ Xato")


@dp.message(Command("ad_off"))
async def cmd_ad_off(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    if await set_ad_status(False):
        await message.answer("✅ Reklama o'chirildi")
    else:
        await message.answer("❌ Xato")


@dp.message(F.text.startswith("/req_add "))
async def cmd_req_add(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    raw = (message.text or "").replace("/req_add", "", 1).strip()
    tokens = raw.split()
    if len(tokens) < 3:
        await message.answer("❌ Format: /req_add CHAT_ID INVITE_LINK KUN [NOM]")
        return
    chat_id = tokens[0].strip()
    rest = [t.strip() for t in tokens[1:] if t.strip()]

    # Link va KUN ni qolgan tokenlardan moslashuvchan topamiz.
    invite_link = None
    invite_idx = -1
    for i, token in enumerate(rest):
        if token.startswith("https://"):
            invite_link = token
            invite_idx = i
            break

    if not invite_link:
        await message.answer("❌ INVITE_LINK topilmadi. https:// bilan boshlansin")
        return

    rest_without_link = rest[:invite_idx] + rest[invite_idx + 1 :]
    day_idx = -1
    digits_only = ""
    for i, token in enumerate(rest_without_link):
        found_digits = "".join(ch for ch in token if ch.isdigit())
        if found_digits:
            digits_only = found_digits
            day_idx = i
            break

    if not digits_only:
        await message.answer("❌ KUN butun son bo'lishi kerak")
        return

    duration_days = int(digits_only)
    if duration_days <= 0:
        await message.answer("❌ KUN 1 yoki undan katta bo'lsin")
        return

    title_tokens = rest_without_link[:]
    if day_idx >= 0:
        title_tokens.pop(day_idx)
    title = " ".join(title_tokens).strip()

    ok, info = await add_required_chat(chat_id, invite_link, title, duration_days)
    if ok:
        await message.answer(
            f"✅ Qo'shildi\nChat ID: {info}\nNom: {title or '-'}\nDavomiylik: {duration_days} kun"
        )
    else:
        await message.answer(f"❌ Qo'shishda xato\n{info}")


@dp.message(F.text.startswith("/req_remove "))
async def cmd_req_remove(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("❌ Format: /req_remove CHAT_ID")
        return
    chat_id = parts[1].strip()
    if await remove_required_chat(chat_id):
        await message.answer(f"✅ O'chirildi: {chat_id}")
    else:
        await message.answer("❌ O'chirishda xato")


@dp.message(Command("req_list"))
async def cmd_req_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    rows = await get_required_chats(active_only=False)
    if not rows:
        await message.answer("ℹ️ Required chatlar yo'q")
        return
    lines = ["🔒 <b>Required chatlar</b>", ""]
    for chat_id, title, invite_link, is_active, expires_at in rows:
        status = "✅ aktiv" if is_active == 1 else "⛔ o'chik"
        exp_text = expires_at or "-"
        lines.append(
            f"ID: <code>{html.escape(str(chat_id))}</code>\n"
            f"Nom: {html.escape(title or '-') }\n"
            f"Link: {html.escape(invite_link)}\n"
            f"Tugash vaqti (UTC): {exp_text}\n"
            f"Holat: {status}\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(F.text.startswith("/req_check "))
async def cmd_req_check(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("❌ Format: /req_check USER_ID")
        return
    try:
        user_id = int(parts[1].strip())
    except Exception:
        await message.answer("❌ USER_ID noto'g'ri")
        return

    report = await debug_required_chats_for_user(user_id)
    if not report:
        await message.answer("ℹ️ Aktiv required chat yo'q")
        return

    lines = [f"🔍 <b>REQ CHECK</b> user_id=<code>{user_id}</code>", ""]
    for item in report:
        state = "✅ OK" if item["ok"] else "❌ NOT OK"
        lines.append(
            f"{state} | {html.escape(item['title'])}\n"
            f"Chat ID: <code>{html.escape(item['chat_id'])}</code>\n"
            f"Status: <b>{html.escape(item['status'])}</b>\n"
            f"Expires: {html.escape(str(item['expires_at'] or '-'))}"
        )
        if item["error"]:
            lines.append(f"Error: <code>{html.escape(item['error'][:300])}</code>")
            lines.append(f"Sabab: {html.escape(explain_req_error(item['error']))}")
        lines.append("")

    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    try:
        async with await connect_db() as db:
            cur = await db.execute(
                "SELECT user_id, full_name, rank, last_activity, bot_blocked FROM users ORDER BY updated_at DESC LIMIT 20"
            )
            users = await cur.fetchall()
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
        return
    if not users:
        await message.answer("👥 Foydalanuvchi yo'q")
        return
    await message.answer("👥 <b>FOYDALANUVCHILAR (20 ta)</b>", parse_mode="HTML")
    for user_id, fname, rank, last_activity, bot_blocked in users:
        blacklisted = await is_blacklisted(user_id)
        now = _now_utc()
        last_dt = _str_to_dt(last_activity)
        if bot_blocked == 1:
            live_status = "⚫ Botdan chiqib ketgan"
        elif last_dt and (now - last_dt).total_seconds() <= 300:
            live_status = "🟢 Online"
        elif last_dt:
            live_status = "🟠 Offline"
        else:
            live_status = "⚪ Noma'lum"

        access_status = "🔴 BLOKLANGAN" if blacklisted else "🟢 AKTIV"
        await message.answer(
            f"🔹 <b>{html.escape(fname or 'Anonim')}</b>\n"
            f"ID: <code>{user_id}</code>\n"
            f"Rank: {rank}\n"
            f"Holat: {access_status}\n"
            f"Faollik: {live_status}",
            parse_mode="HTML",
            reply_markup=admin_user_actions_kb(user_id),
        )


@dp.callback_query(F.data.startswith("admin_user_msg:"))
async def cb_admin_user_msg(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    await state.set_state(AdminMessaging.typing_message)
    await state.update_data(admin_to_id=user_id, admin_to_name=user[2] or "Foydalanuvchi")
    await call.message.answer(
        f"💬 <b>{html.escape(user[2] or 'Foydalanuvchi')}</b> ga admin xabarini yozing:\n\n/cancel bilan bekor qilasiz",
        parse_mode="HTML",
    )
    await call.answer()


@dp.message(StateFilter(AdminMessaging.typing_message))
async def admin_message_send(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("❌ Bekor qilindi")
        return
    data = await state.get_data()
    to_id = data.get("admin_to_id")
    if not to_id:
        await message.answer("❌ Xato")
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Bo'sh xabar yuborilmadi")
        return
    await save_message(ADMIN_ID, to_id, f"[ADMIN] {text}")
    try:
        await bot.send_message(to_id, f"📩 <b>ADMIN XABARI</b>\n\n{html.escape(text)}", parse_mode="HTML")
        await mark_user_bot_blocked(to_id, blocked=False)
    except Exception as e:
        if _is_bot_block_error(e):
            await mark_user_bot_blocked(to_id, blocked=True)
        await message.answer(f"⚠️ DB ga saqlandi, lekin userga yuborilmadi: {e}")
        await state.clear()
        return
    await message.answer("✅ Admin xabari yuborildi")
    await state.clear()


@dp.callback_query(F.data.startswith("admin_user_block:"))
async def cb_admin_user_block(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    ok = await add_to_blacklist(user_id, "Admin paneldan bloklandi")
    if not ok:
        await call.answer("❌ Bloklash xatosi", show_alert=True)
        return
    await call.message.answer(f"🔴 Bloklandi: {html.escape(user[2] or 'Anonim')} ({user_id})", parse_mode="HTML")
    await call.answer("✅ Bloklandi")


@dp.callback_query(F.data.startswith("admin_user_unblock:"))
async def cb_admin_user_unblock(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    ok = await remove_from_blacklist(user_id)
    if not ok:
        await call.answer("❌ Unblock xatosi", show_alert=True)
        return
    await call.message.answer(f"🟢 Unblock qilindi: {html.escape(user[2] or 'Anonim')} ({user_id})", parse_mode="HTML")
    await call.answer("✅ Unblock")


@dp.callback_query(F.data.startswith("admin_user_stat:"))
async def cb_admin_user_stat(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    stats = await get_user_stats(user_id)
    if not stats:
        await call.message.answer("❌ Statistika topilmadi")
        await call.answer()
        return
    total_games, total_wins, total_losses, win_rate, playtime = stats
    ach = await get_user_achievements(user_id)
    text = (
        f"📊 <b>{html.escape(user[2] or 'Anonim')}</b> statistikasi\n"
        f"ID: <code>{user_id}</code>\n\n"
        f"🎮 O'yinlar: <b>{total_games}</b>\n"
        f"✅ G'alaba: <b>{total_wins}</b>\n"
        f"❌ Mag'lubiyat: <b>{total_losses}</b>\n"
        f"🎯 Win Rate: <b>{win_rate:.1f}%</b>\n"
        f"⏱️ Playtime (min): <b>{playtime}</b>\n"
    )
    if ach:
        text += "\n<b>🎖️ Badge'lar:</b>\n"
        for badge_name, emoji, _ in ach[:10]:
            text += f"{emoji} {html.escape(badge_name)}\n"
    await call.message.answer(text, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_clear:"))
async def cb_admin_user_clear(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    ok, total = await clear_user_messages(user_id)
    if not ok:
        await call.answer("❌ Xabarlarni tozalash xatosi", show_alert=True)
        return
    await call.message.answer(
        f"🗑 Tozalandi: {html.escape(user[2] or 'Anonim')} ({user_id})\n"
        f"O'chirilgan xabarlar soni: <b>{total}</b>",
        parse_mode="HTML",
    )
    await call.answer("✅ Tozalandi")


@dp.callback_query(F.data.startswith("admin_user_chat:"))
async def cb_admin_user_chat(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    sent, recv = await get_user_message_audit(user_id, 10)
    lines = [f"📝 <b>CHAT TARIXI</b> - {html.escape(user[2] or 'Anonim')} ({user_id})", ""]
    lines.append("<b>Oxirgi yuborgan xabarlari:</b>")
    if sent:
        for to_id, msg, ts in sent:
            lines.append(f"➡️ {to_id} | {ts}\n{html.escape(msg[:140])}")
    else:
        lines.append("Yo'q")
    lines.append("")
    lines.append("<b>Oxirgi olgan xabarlari:</b>")
    if recv:
        for from_id, msg, ts in recv:
            lines.append(f"⬅️ {from_id} | {ts}\n{html.escape(msg[:140])}")
    else:
        lines.append("Yo'q")
    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_ann:"))
async def cb_admin_user_ann(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    user = await db_get(user_id)
    if not user:
        await call.answer("❌ User topilmadi", show_alert=True)
        return
    logs = await get_announcement_logs(user_id, 20)
    if not logs:
        await call.message.answer("❌ Bu user bo'yicha e'lon log topilmadi")
        await call.answer()
        return
    lines = [f"📢 <b>E'LON TARIXI</b> - {html.escape(user[2] or 'Anonim')} ({user_id})", ""]
    for action, rank, roles, ts in logs:
        lines.append(f"🕒 {ts}\nAction: {action}\nRank: {rank}\nRoles: {html.escape(roles or '[]')}\n")
    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data.startswith("admin_user_req:"))
async def cb_admin_user_req(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Faqat admin uchun", show_alert=True)
        return
    user_id = int(call.data.split(":")[1])
    report = await debug_required_chats_for_user(user_id)
    if not report:
        await call.message.answer("ℹ️ Aktiv required chat yo'q")
        await call.answer()
        return

    lines = [f"🔍 <b>REQ CHECK</b> user_id=<code>{user_id}</code>", ""]
    for item in report:
        state = "✅ OK" if item["ok"] else "❌ NOT OK"
        lines.append(
            f"{state} | {html.escape(item['title'])}\n"
            f"Chat ID: <code>{html.escape(item['chat_id'])}</code>\n"
            f"Status: <b>{html.escape(item['status'])}</b>\n"
            f"Expires: {html.escape(str(item['expires_at'] or '-'))}"
        )
        if item["error"]:
            lines.append(f"Error: <code>{html.escape(item['error'][:300])}</code>")
            lines.append(f"Sabab: {html.escape(explain_req_error(item['error']))}")
        lines.append("")

    await call.message.answer("\n".join(lines), parse_mode="HTML")
    await call.answer()


@dp.message(F.text.startswith("/block "))
async def cmd_block(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    parts = message.text.split(" ", 2)
    if len(parts) < 2:
        await message.answer("❌ Format: /block USER_ID [sabab]")
        return
    try:
        user_id = int(parts[1])
    except Exception:
        await message.answer("❌ USER_ID noto'g'ri")
        return
    reason = parts[2] if len(parts) > 2 else "Admin tomonidan bloklandi"
    user = await db_get(user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi")
        return
    if await add_to_blacklist(user_id, reason):
        await message.answer(f"🔴 BLOKLANDI: {user[2]} ({user_id})\nSabab: {reason}")
    else:
        await message.answer("❌ Xato")


@dp.message(F.text.startswith("/unblock "))
async def cmd_unblock(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    try:
        user_id = int(message.text.split(" ")[1])
    except Exception:
        await message.answer("❌ Format: /unblock USER_ID")
        return
    user = await db_get(user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi")
        return
    if await remove_from_blacklist(user_id):
        await message.answer(f"🟢 BLOKLASH O'CHIRILDI: {user[2]} ({user_id})")
    else:
        await message.answer("❌ Xato")


@dp.message(Command("blacklist"))
async def cmd_blacklist(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    blacklist = await get_blacklist()
    if not blacklist:
        await message.answer("✅ Qora ro'yxat bo'sh")
        return
    text = "🔴 <b>QORA RO'YXAT:</b>\n\n"
    for user_id, reason, timestamp in blacklist:
        user = await db_get(user_id)
        fname = user[2] if user else "O'chirilgan user"
        text += f"🔹 {html.escape(fname)} ({user_id})\n   Sabab: {html.escape(reason)}\n   Vaqt: {timestamp}\n\n"
    await message.answer(text, parse_mode="HTML")


# YANGI ADMIN FUNKSIYA: istalgan payt userga yozish
@dp.message(F.text.startswith("/admin_msg "))
async def cmd_admin_msg(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        await message.answer("❌ Format: /admin_msg USER_ID XABAR")
        return
    try:
        to_id = int(parts[1])
    except Exception:
        await message.answer("❌ USER_ID noto'g'ri")
        return
    text = parts[2].strip()
    if not text:
        await message.answer("❌ Xabar bo'sh")
        return
    await save_message(ADMIN_ID, to_id, f"[ADMIN] {text}")
    try:
        await bot.send_message(to_id, f"📩 <b>ADMIN XABARI</b>\n\n{html.escape(text)}", parse_mode="HTML")
        await mark_user_bot_blocked(to_id, blocked=False)
    except Exception as e:
        if _is_bot_block_error(e):
            await mark_user_bot_blocked(to_id, blocked=True)
        await message.answer(f"⚠️ DB ga saqlandi, lekin userga yuborilmadi: {e}")
        return
    await message.answer("✅ Admin xabari yuborildi")


# YANGI ADMIN FUNKSIYA: user xabar audit
@dp.message(F.text.startswith("/audit_user "))
async def cmd_audit_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    try:
        user_id = int(message.text.split(" ")[1])
    except Exception:
        await message.answer("❌ Format: /audit_user USER_ID")
        return
    user = await db_get(user_id)
    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi")
        return
    sent, recv = await get_user_message_audit(user_id, 10)
    text = [
        f"🔎 <b>AUDIT:</b> {html.escape(user[2] or 'Anonim')} ({user_id})",
        "",
        "<b>Oxirgi yuborgan xabarlari:</b>",
    ]
    if sent:
        for to_id, msg, ts in sent:
            text.append(f"➡️ {to_id} | {ts}\n{html.escape(msg[:120])}")
    else:
        text.append("Yo'q")
    text.append("")
    text.append("<b>Oxirgi olgan xabarlari:</b>")
    if recv:
        for from_id, msg, ts in recv:
            text.append(f"⬅️ {from_id} | {ts}\n{html.escape(msg[:120])}")
    else:
        text.append("Yo'q")
    await message.answer("\n".join(text), parse_mode="HTML")


# YANGI ADMIN FUNKSIYA: qachon, qanday e'lon bergani
@dp.message(F.text.startswith("/announcement_history "))
async def cmd_announcement_history(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    try:
        user_id = int(message.text.split(" ")[1])
    except Exception:
        await message.answer("❌ Format: /announcement_history USER_ID")
        return
    logs = await get_announcement_logs(user_id, 20)
    if not logs:
        await message.answer("❌ E'lon tarixi topilmadi")
        return
    lines = [f"📢 <b>E'LON TARIXI</b> ({user_id})", ""]
    for action, rank, roles, ts in logs:
        lines.append(f"🕒 {ts}\nAction: {action}\nRank: {rank}\nRoles: {roles}\n")
    await message.answer("\n".join(lines), parse_mode="HTML")


@dp.message(Command("add_char"))
async def cmd_add_char(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    await state.set_state(CharacterAdd.name)
    await message.answer("👤 Qahramon nomini yozing:")


@dp.message(StateFilter(CharacterAdd.name))
async def char_name(message: types.Message, state: FSMContext):
    await state.update_data(char_name=message.text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{ro(r)} {r}", callback_data=f"char_add_role:{r}") for r in ROLES[:2]],
            [InlineKeyboardButton(text=f"{ro(r)} {r}", callback_data=f"char_add_role:{r}") for r in ROLES[2:4]],
            [InlineKeyboardButton(text=f"{ro(ROLES[4])} {ROLES[4]}", callback_data=f"char_add_role:{ROLES[4]}")],
        ]
    )
    await state.set_state(CharacterAdd.role)
    await message.answer("🎮 Rol tanlang:", reply_markup=kb)


@dp.callback_query(StateFilter(CharacterAdd.role), F.data.startswith("char_add_role:"))
async def char_role(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":")[1]
    await state.update_data(char_role=role)
    await state.set_state(CharacterAdd.description)
    await call.message.answer(f"✅ Rol: {role}\n📝 Tavsif yozing:")
    await call.answer()


@dp.message(StateFilter(CharacterAdd.description))
async def char_desc(message: types.Message, state: FSMContext):
    await state.update_data(char_description=message.text)
    await state.set_state(CharacterAdd.video_url)
    await message.answer("🎥 Video URL (ixtiyoriy)\n/skip - o'tkazib yuborish")


@dp.message(StateFilter(CharacterAdd.video_url))
async def char_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    video_url = "" if message.text == "/skip" else message.text
    success = await add_character(data.get("char_name"), data.get("char_role"), data.get("char_description"), video_url)
    if success:
        await message.answer(
            f"✅ QAHRAMON QO'SHILDI\n👤 {html.escape(data.get('char_name') or '')}\n🎮 {html.escape(data.get('char_role') or '')}",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Xato yuzaga keldi")
    await state.clear()


# YANGI ADMIN FUNKSIYA: Qahramonni tahrirlash (/edit_char CHAR_ID)
@dp.message(Command("edit_char"))
async def cmd_edit_char(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("❌ Format: /edit_char CHAR_ID")
        return

    try:
        char_id = int(parts[1])
    except Exception:
        await message.answer("❌ CHAR_ID noto'g'ri")
        return

    character = await get_character_by_id(char_id)
    if not character:
        await message.answer("❌ Qahramon topilmadi")
        return

    _, name, role, description, video_url = character
    await state.update_data(
        edit_char_id=char_id,
        edit_old_name=name,
        edit_old_role=role,
        edit_old_description=description,
        edit_old_video_url=video_url or "",
    )
    await state.set_state(CharacterEdit.name)
    await message.answer(
        f"✏️ Joriy nom: {html.escape(name)}\n"
        "Yangi nomni kiriting (o'zgarmasa '-' yuboring):",
        parse_mode="HTML",
    )


@dp.message(StateFilter(CharacterEdit.name))
async def edit_char_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    old_name = data.get("edit_old_name", "")
    new_name = (message.text or "").strip()
    if not new_name:
        await message.answer("❌ Nom bo'sh bo'lmasin")
        return
    if new_name == "-":
        new_name = old_name

    await state.update_data(edit_new_name=new_name)
    await state.set_state(CharacterEdit.role)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{ro(r)} {r}", callback_data=f"char_edit_role:{r}") for r in ROLES[:2]],
            [InlineKeyboardButton(text=f"{ro(r)} {r}", callback_data=f"char_edit_role:{r}") for r in ROLES[2:4]],
            [InlineKeyboardButton(text=f"{ro(ROLES[4])} {ROLES[4]}", callback_data=f"char_edit_role:{ROLES[4]}")],
            [InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="char_edit_role:skip")],
        ]
    )
    await message.answer("🎮 Yangi rolni tanlang yoki o'tkazib yuboring:", reply_markup=kb)


@dp.callback_query(StateFilter(CharacterEdit.role), F.data.startswith("char_edit_role:"))
async def edit_char_role(call: types.CallbackQuery, state: FSMContext):
    role = call.data.split(":", 1)[1]
    data = await state.get_data()
    if role == "skip":
        role = data.get("edit_old_role", "Roamer")
    elif role not in ROLES:
        await call.answer("❌ Noto'g'ri rol", show_alert=True)
        return

    await state.update_data(edit_new_role=role)
    await state.set_state(CharacterEdit.description)
    await call.message.answer("📝 Yangi tavsifni kiriting (o'zgarmasa '-' yuboring):")
    await call.answer()


@dp.message(StateFilter(CharacterEdit.description))
async def edit_char_description(message: types.Message, state: FSMContext):
    data = await state.get_data()
    old_description = data.get("edit_old_description", "")
    description = (message.text or "").strip()
    if not description:
        await message.answer("❌ Tavsif bo'sh bo'lmasin")
        return
    if description == "-":
        description = old_description

    await state.update_data(edit_new_description=description)
    await state.set_state(CharacterEdit.video_url)
    await message.answer("🎥 Yangi video URL kiriting (/skip yoki '-' yuborsangiz eski qiymat qoladi):")


@dp.message(StateFilter(CharacterEdit.video_url))
async def edit_char_video_url(message: types.Message, state: FSMContext):
    data = await state.get_data()
    char_id = data.get("edit_char_id")
    if not char_id:
        await message.answer("❌ Session xatoligi")
        await state.clear()
        return

    old_video = data.get("edit_old_video_url", "")
    raw_video = (message.text or "").strip()
    if raw_video in ("/skip", "-"):
        video_url = old_video
    else:
        video_url = raw_video

    ok = await update_character(
        char_id=char_id,
        name=data.get("edit_new_name", data.get("edit_old_name", "")),
        role=data.get("edit_new_role", data.get("edit_old_role", "Roamer")),
        description=data.get("edit_new_description", data.get("edit_old_description", "")),
        video_url=video_url,
    )
    if not ok:
        await message.answer("❌ Qahramonni yangilashda xato")
        await state.clear()
        return

    await message.answer(f"✅ Qahramon yangilandi (ID: {char_id})")
    await state.clear()


@dp.message(Command("list_chars"))
async def cmd_list_chars(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    characters = await get_all_characters()
    if not characters:
        await message.answer("❌ Qahramon topilmadi")
        return
    text = "🎮 <b>QAHRAMONLAR:</b>\n\n"
    for char_id, name, role, _, _ in characters:
        text += f"🔹 <b>{html.escape(name)}</b> (ID: {char_id})\n   🎮 {role}\n   /edit_char {char_id}\n   /del_char {char_id}\n\n"
    await message.answer(text, parse_mode="HTML")


@dp.message(Command("del_char"))
async def cmd_del_char(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    try:
        char_id = int(message.text.split(" ")[1])
    except Exception:
        await message.answer("❌ Format: /del_char CHAR_ID")
        return
    if await delete_character(char_id):
        await message.answer("✅ Qahramon o'chirildi")
    else:
        await message.answer("❌ Xato")


@dp.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Faqat admin uchun")
        return
    if not os.path.exists(DB):
        await message.answer("❌ DB topilmadi")
        return
    try:
        backup_file = f"mlbb_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        with open(DB, "rb") as src, open(backup_file, "wb") as dst:
            dst.write(src.read())
        await message.answer_document(types.FSInputFile(backup_file), caption="✅ Backup yaratildi")
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")


@dp.callback_query(F.data == "cancel")
async def cb_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Bekor")
    await call.answer()


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor", reply_markup=main_kb())


@dp.callback_query(F.data == "check_join_status")
async def cb_check_join_status(call: types.CallbackQuery):
    if call.from_user.id == ADMIN_ID:
        await call.answer("Admin uchun check shart emas")
        return
    missing = await get_missing_required_chats(call.from_user.id)
    if missing:
        await call.message.answer(
            "❌ Hali hammasiga qo'shilmagansiz. Quyidagi tugmalar orqali qo'shiling.",
            reply_markup=required_join_kb(missing),
        )
        await call.answer("Azo bo'lib qayta tekshiring", show_alert=True)
        return
    await call.message.answer("✅ Tasdiqlandi. Endi botdan foydalanishingiz mumkin.", reply_markup=main_kb())
    await call.answer("OK")


@dp.message()
async def unknown(message: types.Message, state: FSMContext):
    cur = await state.get_state()
    if cur:
        await state.clear()
    await message.answer("❓ Tanilmadi", reply_markup=main_kb())


async def main():
    global ad_worker_task
    # Update-level middleware blacklistni barcha handlerlarga majburiy qo'llaydi.
    dp.update.outer_middleware(BlacklistMiddleware())
    dp.message.middleware(BlacklistMiddleware())
    dp.callback_query.middleware(BlacklistMiddleware())
    await init_db()
    ad_worker_task = asyncio.create_task(ad_worker_loop())
    logger.info("BOT ISHGA TUSHDI")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if ad_worker_task:
            ad_worker_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
