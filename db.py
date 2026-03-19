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
        streak INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        revenge_wins INTEGER DEFAULT 0,
        duel_wins INTEGER DEFAULT 0,
        duel_losses INTEGER DEFAULT 0,
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS revenge_targets (
        chat_id INTEGER,
        loser_id INTEGER,
        target_id INTEGER,
        PRIMARY KEY (chat_id, loser_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS duels (
        chat_id INTEGER,
        challenger_id INTEGER,
        challenger_name TEXT,
        target_id INTEGER,
        target_name TEXT,
        created_at INTEGER,
        PRIMARY KEY (chat_id, challenger_id, target_id)
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
    (chat_id, user_id, username, first_name, plays, survives, losses, streak, best_streak, revenge_wins, duel_wins, duel_losses)
    VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 0, 0, 0)
    """, (chat_id, user_id, username, first_name))

    if survived:
        cur.execute("""
        UPDATE user_stats
        SET username = ?, first_name = ?, plays = plays + 1,
            survives = survives + 1,
            streak = streak + 1,
            best_streak = CASE WHEN streak + 1 > best_streak THEN streak + 1 ELSE best_streak END
        WHERE chat_id = ? AND user_id = ?
        """, (username, first_name, chat_id, user_id))
    else:
        cur.execute("""
        UPDATE user_stats
        SET username = ?, first_name = ?, plays = plays + 1,
            losses = losses + 1,
            streak = 0
        WHERE chat_id = ? AND user_id = ?
        """, (username, first_name, chat_id, user_id))

    conn.commit()
    conn.close()


def get_user_stats(chat_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT plays, survives, losses, streak, best_streak, revenge_wins, duel_wins, duel_losses
    FROM user_stats
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, user_id))
    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "plays": 0,
            "survives": 0,
            "losses": 0,
            "streak": 0,
            "best_streak": 0,
            "revenge_wins": 0,
            "duel_wins": 0,
            "duel_losses": 0
        }

    return {
        "plays": row[0],
        "survives": row[1],
        "losses": row[2],
        "streak": row[3],
        "best_streak": row[4],
        "revenge_wins": row[5],
        "duel_wins": row[6],
        "duel_losses": row[7]
    }


def get_leaderboard(chat_id, limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT first_name, username, survives, losses, plays, best_streak
    FROM user_stats
    WHERE chat_id = ?
    ORDER BY survives DESC, best_streak DESC, plays DESC
    LIMIT ?
    """, (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_streak_leaderboard(chat_id, limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT first_name, username, best_streak
    FROM user_stats
    WHERE chat_id = ?
    ORDER BY best_streak DESC, survives DESC
    LIMIT ?
    """, (chat_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_death_leaderboard(chat_id, limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT first_name, username, losses
    FROM user_stats
    WHERE chat_id = ?
    ORDER BY losses DESC, plays DESC
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


def set_revenge_target(chat_id, loser_id, target_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO revenge_targets (chat_id, loser_id, target_id)
    VALUES (?, ?, ?)
    """, (chat_id, loser_id, target_id))
    conn.commit()
    conn.close()


def get_revenge_target(chat_id, loser_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT target_id FROM revenge_targets
    WHERE chat_id = ? AND loser_id = ?
    """, (chat_id, loser_id))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def add_revenge_win(chat_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR IGNORE INTO user_stats
    (chat_id, user_id, username, first_name, plays, survives, losses, streak, best_streak, revenge_wins, duel_wins, duel_losses)
    VALUES (?, ?, '', '', 0, 0, 0, 0, 0, 0, 0, 0)
    """, (chat_id, user_id))
    cur.execute("""
    UPDATE user_stats
    SET revenge_wins = revenge_wins + 1
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, user_id))
    conn.commit()
    conn.close()


def create_duel(chat_id, challenger_id, challenger_name, target_id, target_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO duels
    (chat_id, challenger_id, challenger_name, target_id, target_name, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (chat_id, challenger_id, challenger_name, target_id, target_name, int(time.time())))
    conn.commit()
    conn.close()


def get_duel_for_target(chat_id, target_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    SELECT challenger_id, challenger_name, target_id, target_name
    FROM duels
    WHERE chat_id = ? AND target_id = ?
    """, (chat_id, target_id))
    row = cur.fetchone()
    conn.close()
    return row


def delete_duel(chat_id, challenger_id, target_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    DELETE FROM duels
    WHERE chat_id = ? AND challenger_id = ? AND target_id = ?
    """, (chat_id, challenger_id, target_id))
    conn.commit()
    conn.close()


def add_duel_result(chat_id, winner_id, loser_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO user_stats
    (chat_id, user_id, username, first_name, plays, survives, losses, streak, best_streak, revenge_wins, duel_wins, duel_losses)
    VALUES (?, ?, '', '', 0, 0, 0, 0, 0, 0, 0, 0)
    """, (chat_id, winner_id))

    cur.execute("""
    INSERT OR IGNORE INTO user_stats
    (chat_id, user_id, username, first_name, plays, survives, losses, streak, best_streak, revenge_wins, duel_wins, duel_losses)
    VALUES (?, ?, '', '', 0, 0, 0, 0, 0, 0, 0, 0)
    """, (chat_id, loser_id))

    cur.execute("""
    UPDATE user_stats
    SET duel_wins = duel_wins + 1
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, winner_id))

    cur.execute("""
    UPDATE user_stats
    SET duel_losses = duel_losses + 1
    WHERE chat_id = ? AND user_id = ?
    """, (chat_id, loser_id))

    conn.commit()
    conn.close()
