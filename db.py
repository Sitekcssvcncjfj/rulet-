import sqlite3
import time

DB_NAME = "bot.db"


def get_conn():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS group_settings (
        chat_id INTEGER PRIMARY KEY,
        enabled INTEGER DEFAULT 1,
        cooldown INTEGER DEFAULT 15,
        loss_chance REAL DEFAULT 0.1666667
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_stats (
        chat_id INTEGER,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        plays INTEGER DEFAULT 0,
        survives INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cooldowns (
        chat_id INTEGER,
        user_id INTEGER,
        last_play INTEGER,
        PRIMARY KEY (chat_id, user_id)
    )
    """)

    conn.commit()
    conn.close()


def ensure_group(chat_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM group_settings WHERE chat_id = ?", (chat_id,))
    row = cur.fetchone()

    if not row:
        cur.execute("""
        INSERT INTO group_settings (chat_id, enabled, cooldown, loss_chance)
        VALUES (?, 1, 15, 0.1666667)
        """, (chat_id,))
        conn.commit()

    conn.close()


def get_group_settings(chat_id):
    ensure_group(chat_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT enabled, cooldown, loss_chance
    FROM group_settings
    WHERE chat_id = ?
    """, (chat_id,))
    row = cur.fetchone()
    conn.close()
    return {
        "enabled": bool(row[0]),
        "cooldown": row[1],
        "loss_chance": row[2]
    }


def set_group_enabled(chat_id, enabled: bool):
    ensure_group(chat_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    UPDATE group_settings SET enabled = ? WHERE chat_id = ?
    """, (1 if enabled else 0, chat_id))
    conn.commit()
    conn.close()


def set_group_cooldown(chat_id, cooldown: int):
    ensure_group(chat_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    UPDATE group_settings SET cooldown = ? WHERE chat_id = ?
    """, (cooldown, chat_id))
    conn.commit()
    conn.close()


def update_user_stats(chat_id, user_id, username, first_name, survived: bool):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO user_stats
    (chat_id, user_id, username, first_name, plays, survives, losses)
    VALUES (?, ?, ?, ?, 0, 0, 0)
    """, (chat_id, user_id, username, first_name))

    cur.execute("""
    UPDATE user_stats
    SET username = ?, first_name = ?, plays = plays + 1,
        survives = survives + ?, losses = losses + ?
    WHERE chat_id = ? AND user_id = ?
    """, (
        username,
        first_name,
        1 if survived else 0,
        0 if survived else 1,
        chat_id,
        user_id
    ))

    conn.commit()
    conn.close()


def get_user_stats(chat_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT plays, survives, losses
    FROM user_stats
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, user_id))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"plays": 0, "survives": 0, "losses": 0}

    return {
        "plays": row[0],
        "survives": row[1],
        "losses": row[2]
    }


def get_leaderboard(chat_id, limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT first_name, username, survives, losses, plays
    FROM user_stats
    WHERE chat_id = ?
    ORDER BY survives DESC, plays DESC
    LIMIT ?
    """, (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_last_play(chat_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT last_play FROM cooldowns
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, user_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0


def set_last_play(chat_id, user_id):
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO cooldowns (chat_id, user_id, last_play)
    VALUES (?, ?, ?)
    """, (chat_id, user_id, now))
    conn.commit()
    conn.close()
