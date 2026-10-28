"""All database access for Chowk. Every SQL statement in the app lives here."""
import hashlib
import os
import re
import secrets
from contextlib import contextmanager
from pathlib import Path

import mysql.connector
from mysql.connector import pooling
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="chowk",
            pool_size=5,
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "social_media"),
        )
    return _pool


@contextmanager
def cursor():
    """Yields a dict cursor; commits on success, rolls back on error."""
    conn = _get_pool().get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def fetch_all(sql, params=None):
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql, params=None):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def ping():
    """Raises if MySQL is unreachable or migration.sql has not been run."""
    fetch_one("SELECT 1 AS ok")
    if not fetch_one("SHOW COLUMNS FROM users LIKE 'password_hash'"):
        raise RuntimeError("Run sql/migration.sql in MySQL Workbench first.")


# ---------------------------------------------------------------- auth
def _hash(password, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.sha256((salt + password).encode()).hexdigest()


def _verify(password, stored):
    if not stored or "$" not in stored:
        return False
    salt = stored.split("$", 1)[0]
    return secrets.compare_digest(_hash(password, salt), stored)


def get_user(user_id):
    return fetch_one(
        "SELECT user_id, username, email, bio, profile_photo_url, created_at "
        "FROM users WHERE user_id = %s", (user_id,))


def register_user(username, email, password, bio=""):
    """INSERT into users + login in one transaction. Raises IntegrityError if the username exists."""
    with cursor() as cur:
        cur.execute(
            "INSERT INTO users(username, email, bio, password_hash) VALUES (%s, %s, %s, %s)",
            (username, email, bio or None, _hash(password)))
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        uid = cur.fetchone()["user_id"]
        cur.execute("INSERT INTO login(user_id, ip) VALUES (%s, %s)", (uid, "127.0.0.1"))
    return get_user(uid)


def login_user(username, password):
    row = fetch_one("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
    if not row or not _verify(password, row["password_hash"]):
        return None
    with cursor() as cur:
        cur.execute("INSERT INTO login(user_id, ip) VALUES (%s, %s)", (row["user_id"], "127.0.0.1"))
    return get_user(row["user_id"])


def update_bio(user_id, bio):
    with cursor() as cur:
        cur.execute("UPDATE users SET bio = %s WHERE user_id = %s", (bio or None, user_id))


# ---------------------------------------------------------------- posts
def get_feed(viewer, mode="everyone", author=None, limit=20):
    where, params = "1 = 1", []
    if mode == "following":
        where = ("(p.user_id IN (SELECT followee_id FROM follows WHERE follower_id = %s) "
                 "OR p.user_id = %s)")
        params = [viewer, viewer]
    elif mode == "user":
        where, params = "p.user_id = %s", [author]
    elif mode == "saved":
        where, params = "p.post_id IN (SELECT post_id FROM bookmarks WHERE user_id = %s)", [viewer]
    sql = f"""
        SELECT p.post_id, p.caption, p.location, p.created_at,
               u.user_id, u.username, u.profile_photo_url, ph.photo_url, vd.video_url,
               (SELECT COUNT(*) FROM post_likes l WHERE l.post_id = p.post_id) AS likes,
               (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) AS comments,
               EXISTS(SELECT 1 FROM post_likes l WHERE l.post_id = p.post_id AND l.user_id = %s) AS liked,
               EXISTS(SELECT 1 FROM bookmarks b WHERE b.post_id = p.post_id AND b.user_id = %s) AS saved,
               (SELECT GROUP_CONCAT(TRIM(h.hashtag_name) SEPARATOR ' ')
                  FROM post_tags pt JOIN hashtags h ON h.hashtag_id = pt.hashtag_id
                 WHERE pt.post_id = p.post_id) AS tags
        FROM post p
        INNER JOIN users u ON u.user_id = p.user_id
        LEFT JOIN photos ph ON ph.photo_id = p.photo_id
        LEFT JOIN videos vd ON vd.video_id = p.video_id
        WHERE {where}
        ORDER BY p.created_at DESC, p.post_id DESC
        LIMIT %s"""
    return fetch_all(sql, [viewer, viewer] + params + [limit])


def create_post(user_id, caption, location, photo_url):
    """post + photo + hashtags written as ONE transaction."""
    with cursor() as cur:
        cur.execute("INSERT INTO post(user_id, caption, location) VALUES (%s, %s, %s)",
                    (user_id, caption, location or None))
        cur.execute("SELECT post_id FROM post WHERE user_id = %s ORDER BY post_id DESC LIMIT 1", (user_id,))
        pid = cur.fetchone()["post_id"]
        if photo_url:
            cur.execute("INSERT INTO photos(photo_url, post_id) VALUES (%s, %s)", (photo_url, pid))
            cur.execute("UPDATE post SET photo_id = %s WHERE post_id = %s", (cur.lastrowid, pid))
        for tag in set(t.lower() for t in re.findall(r"#(\w+)", caption)):
            cur.execute("SELECT hashtag_id FROM hashtags WHERE LOWER(TRIM(hashtag_name)) = %s",
                        ("#" + tag,))
            row = cur.fetchone()
            if row:
                hid = row["hashtag_id"]
            else:
                cur.execute("INSERT INTO hashtags(hashtag_name) VALUES (%s)", ("#" + tag,))
                hid = cur.lastrowid
            cur.execute("INSERT IGNORE INTO post_tags(post_id, hashtag_id) VALUES (%s, %s)", (pid, hid))
    return pid


def _toggle(table, delete_sql, insert_sql, params):
    with cursor() as cur:
        cur.execute(delete_sql, params)
        if cur.rowcount == 0:
            cur.execute(insert_sql, params)


def toggle_like(user_id, post_id):
    _toggle("post_likes",
            "DELETE FROM post_likes WHERE user_id = %s AND post_id = %s",
            "INSERT INTO post_likes(user_id, post_id) VALUES (%s, %s)", (user_id, post_id))


def toggle_bookmark(user_id, post_id):
    _toggle("bookmarks",
            "DELETE FROM bookmarks WHERE user_id = %s AND post_id = %s",
            "INSERT INTO bookmarks(user_id, post_id) VALUES (%s, %s)", (user_id, post_id))


def toggle_follow(follower_id, followee_id):
    if follower_id == followee_id:
        return
    _toggle("follows",
            "DELETE FROM follows WHERE follower_id = %s AND followee_id = %s",
            "INSERT INTO follows(follower_id, followee_id) VALUES (%s, %s)",
            (follower_id, followee_id))


def add_comment(post_id, user_id, text):
    with cursor() as cur:
        cur.execute("INSERT INTO comments(comment_text, post_id, user_id) VALUES (%s, %s, %s)",
                    (text, post_id, user_id))


def get_comments(post_id, limit=30):
    return fetch_all(
        "SELECT u.username, c.comment_text, c.created_at FROM comments c "
        "INNER JOIN users u ON u.user_id = c.user_id "
        "WHERE c.post_id = %s ORDER BY c.comment_id DESC LIMIT %s", (post_id, limit))


# ---------------------------------------------------------------- people
def get_people(viewer, search=""):
    return fetch_all(
        """SELECT u.user_id, u.username, u.bio, u.profile_photo_url,
                  s.posts, s.followers, s.following,
                  EXISTS(SELECT 1 FROM follows f
                          WHERE f.follower_id = %s AND f.followee_id = u.user_id) AS is_following
           FROM users u
           INNER JOIN vw_user_stats s ON s.user_id = u.user_id
           WHERE u.user_id <> %s AND u.username LIKE %s
           ORDER BY s.followers DESC, u.username
           LIMIT 30""", (viewer, viewer, "%" + search + "%"))


def get_stats(user_id):
    return fetch_one("SELECT posts, followers, following FROM vw_user_stats WHERE user_id = %s",
                     (user_id,))


def get_connections(user_id, kind):
    if kind == "followers":
        sql = ("SELECT u.username FROM follows f INNER JOIN users u ON u.user_id = f.follower_id "
               "WHERE f.followee_id = %s ORDER BY f.created_at DESC")
    else:
        sql = ("SELECT u.username FROM follows f INNER JOIN users u ON u.user_id = f.followee_id "
               "WHERE f.follower_id = %s ORDER BY f.created_at DESC")
    return [r["username"] for r in fetch_all(sql, (user_id,))]


# ---------------------------------------------------------------- live database view
TABLES = ["users", "post", "photos", "comments", "post_likes", "comment_likes", "follows",
          "bookmarks", "hashtags", "hashtag_follow", "post_tags", "login", "activity_log"]
_ORDER = {"login": "login_id DESC", "post_tags": "post_id DESC", "post_likes": "created_at DESC"}


def table_counts():
    return [{"table": t, "rows": fetch_one(f"SELECT COUNT(*) AS c FROM {t}")["c"]} for t in TABLES]


def table_preview(table, limit=25):
    if table not in TABLES:
        raise ValueError("Unknown table")
    if table == "users":  # never show password hashes
        sql = "SELECT user_id, username, email, bio, created_at FROM users ORDER BY user_id DESC LIMIT %s"
    else:
        sql = f"SELECT * FROM {table} ORDER BY {_ORDER.get(table, 'created_at DESC')} LIMIT %s"
    return fetch_all(sql, (limit,))


def recent_activity(limit=50):
    return fetch_all(
        "SELECT a.log_id, a.created_at, COALESCE(u.username, '-') AS user, a.action, a.details "
        "FROM activity_log a LEFT JOIN users u ON u.user_id = a.user_id "
        "ORDER BY a.log_id DESC LIMIT %s", (limit,))


# ---------------------------------------------------------------- query lab
def load_queries(path=None):
    """Parses sql/queries.sql. Header format:  -- #N | Title | Concept"""
    path = path or Path(__file__).parent / "sql" / "queries.sql"
    items, current = [], None
    for line in open(path, encoding="utf-8"):
        m = re.match(r"--\s*#(\d+)\s*\|\s*(.+?)\s*\|\s*(.+)", line)
        if m:
            current = {"no": int(m.group(1)), "title": m.group(2), "concept": m.group(3).strip(), "sql": ""}
            items.append(current)
        elif current is not None:
            current["sql"] += line
    for q in items:
        q["sql"] = q["sql"].strip().rstrip(";").strip()
    return items


def run_select(sql):
    if not re.match(r"^\s*(select|with)\b", sql, re.I) or ";" in sql.strip().rstrip(";"):
        raise ValueError("The query lab only runs a single SELECT / WITH statement.")
    with cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()