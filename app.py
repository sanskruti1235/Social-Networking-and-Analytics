"""Chowk - a small social network on MySQL.  Run:  streamlit run app.py"""
import base64
import hashlib
import html
import re
import urllib.request
from datetime import datetime
from pathlib import Path

import mysql.connector
import altair as alt
import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="Chowk", page_icon="💬", layout="wide")
st.markdown("<style>" + (Path(__file__).parent / "style.css").read_text(encoding="utf-8") + "</style>",
            unsafe_allow_html=True)

PAGES = ["Feed", "New post", "People", "Saved", "My profile", "Live database", "Query lab"]


# ------------------------------------------------------------------ helpers
def esc(x):
    return html.escape(str(x or ""))


def avatar(url, name, size=40):
    face = esc((name or "?")[:1].upper())
    img = ""
    if url and str(url).startswith("http"):
        img = '<img src="' + esc(url) + '" alt="" onerror="this.remove()">'
    return ('<span class="av" style="--s:' + str(size) + 'px"><span class="face">' + face + img
            + "</span></span>")


def hd(url):
    """Seed photos are picsum.photos/<n> (n x n px). Ask for a proper wide image instead."""
    m = re.match(r"https://picsum\.photos/(\d+)$", url or "")
    return "https://picsum.photos/seed/" + m.group(1) + "/800/1000" if m else url


@st.cache_data(ttl=300, show_spinner=False)
def picsum_ok():
    """True if the placeholder-photo site is reachable from this network."""
    try:
        urllib.request.urlopen(urllib.request.Request("https://picsum.photos/seed/1/40/50",
                               headers={"User-Agent": "Mozilla/5.0"}), timeout=2).read(256)
        return True
    except Exception:
        return False


def art(seed, caption):
    """Poster-style picture drawn locally (no internet) for posts whose photo can't load."""
    h = int(hashlib.md5(str(seed).encode()).hexdigest(), 16)
    bg, fg, blob = [("#F0348C", "#141012", "#F6F1E7"), ("#141012", "#F0348C", "#2A1620"),
                    ("#F6F1E7", "#141012", "#F0348C"), ("#2A1620", "#F6F1E7", "#F0348C")][h % 4]
    cx, cy, r = 150 + (h >> 4) % 500, 150 + (h >> 12) % 400, 200 + (h >> 20) % 150
    lines, cur = [], ""
    for w in re.sub(r"[^\w\s#!?.,']", "", caption or "").upper().split():
        if cur and len(cur) + len(w) + 1 > 11:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    lines = lines[:6] or ["CHOWK"]
    y0 = 930 - 110 * (len(lines) - 1)
    text = "".join('<text x="60" y="%d" font-family="Impact,Anton,sans-serif" font-size="96" fill="%s">%s</text>'
                   % (y0 + 110 * i, fg, html.escape(line)) for i, line in enumerate(lines))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 1000"><rect width="800" height="1000" fill="'
           + bg + '"/><circle cx="' + str(cx) + '" cy="' + str(cy) + '" r="' + str(r) + '" fill="' + blob + '"/>'
           + text + "</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def media_src(p):
    url = p["photo_url"]
    if "picsum.photos" in url and not picsum_ok():
        return art(p["post_id"], p["caption"])
    return hd(url)


def ago(dt):
    if not dt:
        return ""
    s = int((datetime.now() - dt).total_seconds())
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if s >= size:
            return str(s // size) + unit + " ago"
    return "just now"


def banner(title, sub="", lead=""):
    st.markdown('<div class="banner">' + lead + "<div><span>" + esc(title) + "</span><small>" + esc(sub)
                + "</small></div></div>", unsafe_allow_html=True)


def show_table(df, max_rows=200):
    """Own HTML table so colours never depend on the Streamlit theme."""
    if df.empty:
        st.info("No rows to show yet.")
        return
    raw = df.head(max_rows).to_html(index=False, border=0, classes="tbl", escape=True, na_rep="")
    st.markdown('<div class="tbl-wrap">' + re.sub(r">\s+<", "><", raw) + "</div>", unsafe_allow_html=True)


def tile(label, value):
    return '<div class="tile"><b>' + esc(value) + "</b><span>" + esc(label) + "</span></div>"


def flash_db_error(e):
    st.error("Database said: " + getattr(e, "msg", str(e)))


# ------------------------------------------------------------------ auth
def auth_page():
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        st.markdown('<div class="poster"><h1>Meet at<br>the chowk.</h1>'
                    '<svg viewBox="0 0 300 250" fill="none" stroke="#F6F1E7" stroke-width="9" stroke-linecap="round" '
                    'stroke-linejoin="round"><path d="M40 62C62 18 240 14 262 70C286 126 254 176 204 186L190 234L146 191'
                    'C90 196 30 170 28 121C27 96 32 76 40 62Z"/><path d="M84 96H214M84 132H184"/></svg>'
                    '<div class="bar">Post a moment. Follow your people.</div></div>', unsafe_allow_html=True)
    with right:
        tab_in, tab_up = st.tabs(["Log in", "Create account"])
        with tab_in:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                go = st.form_submit_button("Log in")
            st.caption("Trying it out? Use any existing username with password chowk123.")
            if go:
                user = db.login_user(username.strip(), password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                st.error("Username or password is incorrect.")
        with tab_up:
            with st.form("register_form"):
                new_name = st.text_input("Choose a username", max_chars=30)
                email = st.text_input("Email", max_chars=100)
                bio = st.text_input("Bio (optional)", max_chars=255)
                pw = st.text_input("Password (6+ characters)", type="password")
                create = st.form_submit_button("Create account")
            if create:
                new_name = new_name.strip()
                if len(new_name) < 3:
                    st.error("Username needs at least 3 characters.")
                elif "@" not in email or "." not in email:
                    st.error("Enter a valid email address.")
                elif len(pw) < 6:
                    st.error("Password needs at least 6 characters.")
                else:
                    try:
                        st.session_state.user = db.register_user(new_name, email.strip(), pw, bio.strip())
                        st.rerun()
                    except mysql.connector.IntegrityError:
                        st.error("That username is taken. Try another.")


def logout():
    st.session_state.user = None


# ------------------------------------------------------------------ post card
def render_post(p, uid, ctx):
    pid = p["post_id"]
    liked, saved = bool(p["liked"]), bool(p["saved"])
    with st.container(key="post_" + ctx + "_" + str(pid)):
        place = ('<small>' + esc(p["location"]) + "</small>") if p["location"] else ""
        st.markdown('<div class="phead">' + avatar(p["profile_photo_url"], p["username"]) + "<div><b>"
                    + esc(p["username"]) + "</b>" + place + '</div><span class="when">'
                    + ago(p["created_at"]) + "</span></div>", unsafe_allow_html=True)
        if p["photo_url"]:
            st.image(media_src(p))
        if p["video_url"]:
            if st.toggle("Watch video", key="vid_" + ctx + "_" + str(pid)):
                st.video(p["video_url"])
        st.markdown('<div class="caption">' + esc(p["caption"]) + "</div>", unsafe_allow_html=True)
        if p["tags"]:
            st.markdown('<div class="tags">' + "".join("<span>" + esc(t) + "</span>" for t in p["tags"].split())
                        + "</div>", unsafe_allow_html=True)

        a, b, _ = st.columns([1, 1, 4])
        a.button(("♥ " if liked else "♡ ") + str(p["likes"]),
                 key="like" + ("on" if liked else "off") + "_" + ctx + "_" + str(pid),
                 on_click=db.toggle_like, args=(uid, pid))
        b.button("Saved" if saved else "Save",
                 key="save" + ("on" if saved else "off") + "_" + ctx + "_" + str(pid),
                 on_click=db.toggle_bookmark, args=(uid, pid))

        with st.expander("Comments (" + str(p["comments"]) + ")"):
            for c in db.get_comments(pid):
                st.markdown('<div class="cmt"><b>' + esc(c["username"]) + "</b> " + esc(c["comment_text"])
                            + "</div>", unsafe_allow_html=True)
            with st.form("cf_" + ctx + "_" + str(pid), clear_on_submit=True):
                text = st.text_input("Add a comment", max_chars=255, label_visibility="collapsed",
                                     placeholder="Add a comment")
                sent = st.form_submit_button("Comment")
            if sent and text.strip():
                db.add_comment(pid, uid, text.strip())
                st.rerun()


def render_posts(posts, uid, ctx, empty):
    if not posts:
        st.info(empty)
    for p in posts:
        render_post(p, uid, ctx)


# ------------------------------------------------------------------ pages
def page_new_post(me):
    banner("New post", "Share a photo and a few words with everyone")
    with st.container(key="post_composer"):
        st.markdown('<div class="phead"><b>Share a moment</b></div>', unsafe_allow_html=True)
        with st.form("new_post", clear_on_submit=True):
            caption = st.text_area("Caption", max_chars=200, placeholder="What did you see today? Add #hashtags")
            c1, c2 = st.columns(2)
            location = c1.text_input("Location (optional)", max_chars=50)
            image = c2.text_input("Image link (optional)")
            sent = st.form_submit_button("Post")
        if sent:
            if not caption.strip():
                st.warning("Write a caption first.")
            else:
                try:
                    db.create_post(me["user_id"], caption.strip(), location.strip(), image.strip())
                    st.success("Posted. Open Feed to see it.")
                except mysql.connector.Error as e:
                    flash_db_error(e)


def page_feed(me):
    banner("Feed", "Moments from everyone, or just the people you follow")
    mode = st.radio("Show", ["Everyone", "Following"], horizontal=True, label_visibility="collapsed")
    posts = db.get_feed(me["user_id"], mode.lower())
    render_posts(posts, me["user_id"], "feed",
                 "Nothing here yet. Follow a few people from the People page and their posts will show up.")


def page_people(me):
    banner("People", "Find someone worth following")
    q = st.text_input("Search people", placeholder="Search by username", label_visibility="collapsed")
    people = db.get_people(me["user_id"], q.strip())
    if not people:
        st.info("No one matches that name.")
    cols = st.columns(3)
    for i, p in enumerate(people):
        following = bool(p["is_following"])
        with cols[i % 3]:
            with st.container(key="person_" + str(p["user_id"])):
                st.markdown('<div class="phead">' + avatar(p["profile_photo_url"], p["username"], 48)
                            + "<div><b>" + esc(p["username"]) + '</b></div></div><div class="bio">'
                            + esc(p["bio"]) + '</div><div class="nums"><span><b>' + str(p["posts"])
                            + "</b> posts</span><span><b>" + str(p["followers"]) + "</b> followers</span><span><b>"
                            + str(p["following"]) + "</b> following</span></div>", unsafe_allow_html=True)
                st.button("Following" if following else "Follow",
                          key=("followon_" if following else "followoff_") + str(p["user_id"]),
                          on_click=db.toggle_follow, args=(me["user_id"], p["user_id"]))


def page_saved(me):
    banner("Saved", "Posts you kept for later")
    render_posts(db.get_feed(me["user_id"], "saved"), me["user_id"], "saved",
                 "You haven't saved anything. Tap Save on a post to keep it here.")


def page_profile(me):
    user = db.get_user(me["user_id"])
    stats = db.get_stats(me["user_id"])
    banner(user["username"], user["bio"] or "No bio yet.", avatar(user["profile_photo_url"], user["username"], 80))
    c1, c2, c3 = st.columns(3)
    c1.markdown(tile("Posts", stats["posts"]), unsafe_allow_html=True)
    c2.markdown(tile("Followers", stats["followers"]), unsafe_allow_html=True)
    c3.markdown(tile("Following", stats["following"]), unsafe_allow_html=True)
    with st.expander("Edit bio"):
        with st.form("bio_form"):
            new_bio = st.text_input("Bio", value=user["bio"] or "", max_chars=255)
            if st.form_submit_button("Save bio"):
                db.update_bio(me["user_id"], new_bio.strip())
                st.rerun()
    t_posts, t_fers, t_fing = st.tabs(["Posts", "Followers", "Following"])
    with t_posts:
        render_posts(db.get_feed(me["user_id"], "user", author=me["user_id"]), me["user_id"], "mine",
                     "You haven't posted yet. Share your first moment from the Feed.")
    for tab, kind in ((t_fers, "followers"), (t_fing, "following")):
        with tab:
            names = db.get_connections(me["user_id"], kind)
            st.markdown("".join('<span class="chip">' + esc(n) + "</span>" for n in names)
                        or "Nobody yet.", unsafe_allow_html=True)


def to_df(rows):
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].dtype == object:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass
    return df


def page_live():
    banner("Live database", "Every action in the app, as MySQL sees it")
    st.caption("Do something in the app (post, like, follow), come back here and press Refresh.")
    st.button("Refresh")
    t_counts, t_log, t_browse = st.tabs(["Row counts", "Activity log", "Browse tables"])
    with t_counts:
        counts = db.table_counts()
        cols = st.columns(4)
        for i, c in enumerate(counts):
            cols[i % 4].markdown(tile(c["table"], c["rows"]), unsafe_allow_html=True)
    with t_log:
        st.caption("Filled automatically by MySQL triggers.")
        show_table(to_df(db.recent_activity()))
    with t_browse:
        table = st.selectbox("Table", db.TABLES)
        show_table(to_df(db.table_preview(table)))


def page_lab():
    banner("Query lab", "26 SQL queries you can run and edit")
    queries = db.load_queries()
    q = st.selectbox("Query", queries, format_func=lambda x: "#" + str(x["no"]) + "  " + x["title"])
    st.caption("Concepts: " + q["concept"])
    sql = st.text_area("SQL (editable, SELECT / WITH only)", value=q["sql"], height=220,
                       key="sql_" + str(q["no"]))
    if st.button("Run query"):
        try:
            rows = db.run_select(sql)
        except (ValueError, mysql.connector.Error) as e:
            st.error(getattr(e, "msg", str(e)))
            return
        if not rows:
            st.info("The query ran but returned no rows.")
            return
        df = to_df(rows)
        st.caption(str(len(df)) + " rows")
        show_table(df)
        nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not c.endswith("id")]
        labels = [c for c in df.columns if c not in nums and not c.endswith("id")
                  and not pd.api.types.is_datetime64_any_dtype(df[c])]
        if len(df) > 1 and nums and labels:
            chart = (alt.Chart(df.head(30))
                     .mark_bar(color="#F0348C", stroke="#141012", strokeWidth=2)
                     .encode(x=alt.X(labels[0] + ":N", sort="-y", axis=alt.Axis(labelAngle=-35, labelLimit=160)),
                             y=alt.Y(nums[0] + ":Q"))
                     .properties(height=340)
                     .configure(background="#FFFDF7")
                     .configure_axis(labelColor="#141012", titleColor="#141012", gridColor="#E4DCCB",
                                     domainColor="#141012", tickColor="#141012", labelFont="Archivo"))
            st.altair_chart(chart, theme=None)


# ------------------------------------------------------------------ main
if "user" not in st.session_state:
    st.session_state.user = None

try:
    db.ping()
except Exception as e:
    st.error("Can't reach the database: " + str(e))
    st.stop()

if st.session_state.user is None:
    auth_page()
else:
    me = st.session_state.user
    with st.sidebar:
        st.markdown('<div class="brand">Chowk</div><div class="me">' + avatar(me["profile_photo_url"], me["username"], 44)
                    + "<div><b>" + esc(me["username"]) + "</b><small>" + esc(me["email"]) + "</small></div></div>",
                    unsafe_allow_html=True)
        page = st.radio("Go to", PAGES, label_visibility="collapsed")
        st.button("Log out", on_click=logout)
    {"Feed": lambda: page_feed(me), "New post": lambda: page_new_post(me), "People": lambda: page_people(me), "Saved": lambda: page_saved(me),
     "My profile": lambda: page_profile(me), "Live database": page_live, "Query lab": page_lab}[page]()