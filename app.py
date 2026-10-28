"""Chowk - a small social network on MySQL.  Run:  streamlit run app.py"""
import base64
import hashlib
import html
import re
import secrets
import urllib.request
from pathlib import Path
from datetime import datetime

import mysql.connector
import altair as alt
import pandas as pd
import streamlit as st

import db

# ---------------------------------------------------------------------------
# Look and feel (poster / zine style). Streamlit styles pages through CSS, so it
# lives here as a Python string: no separate .css file is needed.
# ---------------------------------------------------------------------------
CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@400;500;700&family=Rubik+Dirt&display=swap');

:root { --ink:#141012; --pink:#F0348C; --paper:#F6F1E7; --card:#FFFDF7; --muted:#5B4A50; }

html, body, .stApp, [class*="css"] { font-family:'Archivo', sans-serif; color:var(--ink); }
.stApp { background:var(--paper); }
header[data-testid="stHeader"] { background:transparent; }
#MainMenu, footer { visibility:hidden; }
.block-container { padding-top:2rem; max-width:1100px; }
h1, h2, h3 { font-family:'Anton', sans-serif; font-weight:400; text-transform:uppercase; line-height:.95; }

/* ---------- page banner (black poster with pink type) ---------- */
.banner { display:flex; gap:1.2rem; align-items:center; background:var(--ink); border:3px solid var(--ink);
          box-shadow:8px 8px 0 var(--pink); padding:1.2rem 1.5rem 1rem; margin:0 0 2rem; }
.banner span { display:block; font-family:'Anton', sans-serif; font-size:clamp(3rem, 7vw, 5.5rem);
               line-height:.95; color:var(--pink); text-transform:uppercase; overflow-wrap:anywhere; }
.banner small { display:block; margin-top:.5rem; color:var(--paper); font-size:1rem; }

/* ---------- login poster ---------- */
.poster { background:var(--pink); border:3px solid var(--ink); box-shadow:10px 10px 0 var(--ink); padding:1.6rem; }
.poster h1 { font-size:clamp(3.8rem, 8vw, 7rem); color:var(--ink); margin:0 0 .6rem; padding:0; }
.poster svg { width:55%; display:block; margin:0 0 1.2rem; }
.bar { display:inline-block; background:var(--paper); border:3px solid var(--ink); box-shadow:4px 4px 0 var(--ink);
       padding:.4rem .9rem; font-family:'Anton', sans-serif; font-size:1.3rem; text-transform:uppercase; }

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] { background:var(--ink); border-right:3px solid var(--pink); }
section[data-testid="stSidebar"] * { color:var(--paper); }
.brand { font-family:'Rubik Dirt', 'Anton', sans-serif; font-size:3rem; line-height:1; color:var(--pink) !important; margin:0 0 .8rem; }
.me { display:flex; gap:.7rem; align-items:center; padding:.4rem 0 1.2rem; }
.me b { display:block; } .me small { color:#BBA9B0 !important; }
section[data-testid="stSidebar"] [role="radiogroup"] label p { font-family:'Anton', sans-serif; font-size:1.35rem;
          text-transform:uppercase; letter-spacing:.03em; }
section[data-testid="stSidebar"] .stButton > button { background:var(--pink); color:var(--ink); border-color:var(--paper);
          box-shadow:3px 3px 0 var(--paper); }
section[data-testid="stSidebar"] .stButton > button p { color:var(--ink); }

/* ---------- blob avatar ---------- */
.av { display:inline-block; width:var(--s,40px); height:var(--s,40px); padding:3px; flex:none; background:var(--pink);
      border-radius:46% 54% 52% 48% / 55% 45% 55% 45%; }
.av .face { position:relative; width:100%; height:100%; overflow:hidden; box-sizing:border-box; border-radius:inherit;
            border:2px solid var(--ink); background:var(--ink); color:var(--pink); display:grid; place-items:center;
            font-family:'Anton', sans-serif; font-size:calc(var(--s,40px) * .45); }
.av img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }

/* ---------- cards (st.container key="post_..." / "person_...") ---------- */
[class*="st-key-post_"], [class*="st-key-person_"] { background:var(--card); border:3px solid var(--ink);
      box-shadow:6px 6px 0 var(--ink); padding:1.1rem 1.2rem; margin-bottom:1rem; }
.phead { display:flex; gap:.8rem; align-items:center; margin-bottom:.8rem; }
.phead b { display:block; font-family:'Anton', sans-serif; font-weight:400; font-size:1.35rem;
           text-transform:uppercase; line-height:1; }
.phead small { color:var(--muted); }
.when { margin-left:auto; font-size:.8rem; color:var(--muted); }
.imgwrap { background:var(--pink); border:3px solid var(--ink); margin-bottom:.8rem; line-height:0; }
.post-img { width:100%; max-height:520px; object-fit:cover; display:block;
            filter:grayscale(1) contrast(1.15); mix-blend-mode:multiply; }
.caption { margin:.2rem 0 .5rem; font-size:1.15rem; font-weight:700; line-height:1.35; }
.tags span { display:inline-block; margin:0 .4rem .4rem 0; padding:.05rem .55rem; border:2px solid var(--ink);
             background:var(--pink); font-weight:700; font-size:.82rem; }
.cmt { padding:.45rem 0; border-bottom:2px solid var(--ink); font-size:.95rem; }
.cmt:last-child { border-bottom:0; }
.bio { color:var(--muted); font-size:.92rem; min-height:2.8em; margin:.2rem 0 .6rem; }
.nums { display:flex; gap:1.2rem; font-size:.85rem; color:var(--muted); margin-bottom:.7rem; }
.nums b { color:var(--ink); font-family:'Anton', sans-serif; font-weight:400; font-size:1.3rem; }
.chip { display:inline-block; background:var(--card); border:2px solid var(--ink); padding:.15rem .7rem;
        margin:0 .5rem .5rem 0; font-weight:700; font-size:.9rem; }

/* ---------- buttons ---------- */
.stButton > button, .stFormSubmitButton > button,
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stBaseButton-primary"] {
      border-radius:0; border:3px solid var(--ink); background:var(--paper); color:var(--ink); font-weight:700;
      box-shadow:3px 3px 0 var(--ink); transition:none; }
.stButton > button:hover, .stFormSubmitButton > button:hover { background:var(--pink); color:var(--ink); border-color:var(--ink); }
.stButton > button:active, .stFormSubmitButton > button:active { box-shadow:none; transform:translate(3px,3px); }
.stButton > button p, .stFormSubmitButton > button p { color:inherit; }
.stFormSubmitButton > button, [class*="st-key-followoff_"] button, [class*="st-key-likeon_"] button { background:var(--pink); }
[class*="st-key-followon_"] button { background:var(--ink); color:var(--pink); }

/* ---------- inputs, tabs, expanders, metrics ---------- */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div { border-radius:0 !important;
      border:2px solid var(--ink) !important; background:var(--card) !important; }
[data-testid="stExpander"] { border:2px solid var(--ink); border-radius:0; background:var(--card); }
button[data-baseweb="tab"] p { font-family:'Anton', sans-serif; font-size:1.25rem; text-transform:uppercase; letter-spacing:.03em; }
[data-baseweb="tab-highlight"] { background:var(--pink) !important; height:4px !important; }
[data-testid="stMetric"] { background:var(--card); border:3px solid var(--ink); box-shadow:4px 4px 0 var(--ink); padding:.6rem 1rem; }
[data-testid="stMetricValue"] { font-family:'Anton', sans-serif; color:var(--pink); font-size:2.8rem; }

@media (prefers-reduced-motion: reduce) { * { transition:none !important; animation:none !important; } }


/* =====================================================================
   READABILITY GUARD - forces readable colours even if the browser / OS is
   in dark mode or the Streamlit theme file is not picked up.
   ===================================================================== */
:root { color-scheme: light; }
.stApp, .stApp [class*="css"] { color:var(--ink) !important; }
.stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stWidgetLabel"] p, .stApp label, .stApp label p,
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p,
.stApp [data-testid="stMetricLabel"] p, .stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stExpander"] summary, .stApp [data-testid="stExpander"] summary p,
.stApp button[data-baseweb="tab"], .stApp button[data-baseweb="tab"] p,
.stApp [data-testid="stAlert"] p, .stApp [data-testid="stAlert"] { color:var(--ink) !important; }

/* inputs */
.stApp input, .stApp textarea { color:var(--ink) !important; -webkit-text-fill-color:var(--ink) !important;
      caret-color:var(--ink); background:var(--card) !important; }
.stApp input::placeholder, .stApp textarea::placeholder { color:#7A6A70 !important; -webkit-text-fill-color:#7A6A70 !important; opacity:1; }
[data-baseweb="select"] *, [data-baseweb="popover"] *, [data-baseweb="menu"] * { color:var(--ink) !important; }
[data-baseweb="popover"] ul, [data-baseweb="menu"], ul[role="listbox"] { background:var(--card) !important; }

/* info / warning / error boxes */
[data-testid="stAlert"] { background:var(--card) !important; border:2px solid var(--ink); border-radius:0; }

/* tables */
[data-testid="stDataFrame"] { border:3px solid var(--ink); background:var(--card); }

/* re-assert the intentional exceptions (pink / paper text on dark or pink blocks) */
.banner span, .stApp .banner span { color:var(--pink) !important; }
.banner small, .stApp .banner small { color:var(--paper) !important; }
.poster h1, .stApp .poster h1, .bar, .stApp .bar { color:var(--ink) !important; }
.av .face { color:var(--pink) !important; }
.tags span, .stApp .tags span { color:var(--ink) !important; }
.phead small, .when, .bio, .nums { color:var(--muted) !important; }
.nums b, .phead b { color:var(--ink) !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div { color:var(--pink) !important; }

/* buttons: ink text on paper / pink; pink text on the black "Following" button */
.stApp .stButton > button, .stApp .stFormSubmitButton > button,
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stBaseButton-secondaryFormSubmit"],
.stApp [data-testid="stBaseButton-primary"], .stApp .stButton > button p, .stApp .stFormSubmitButton > button p,
.stApp [data-testid^="stBaseButton"] p { color:var(--ink) !important; }
.stApp [class*="st-key-followon_"] button, .stApp [class*="st-key-followon_"] button p { color:var(--pink) !important; }

/* sidebar: paper text on black; ink text on the pink Log out button */
section[data-testid="stSidebar"] *, section[data-testid="stSidebar"] label p { color:var(--paper) !important; }
section[data-testid="stSidebar"] .brand { color:var(--pink) !important; }
section[data-testid="stSidebar"] .me small { color:#BBA9B0 !important; }
section[data-testid="stSidebar"] .stButton > button, section[data-testid="stSidebar"] .stButton > button p,
section[data-testid="stSidebar"] [data-testid^="stBaseButton"] p { color:var(--ink) !important; }
section[data-testid="stSidebar"] .av .face { color:var(--pink) !important; }

/* ---------- own table + stat tiles (no Streamlit theme involved) ---------- */
.tbl-wrap { overflow:auto; max-height:520px; background:var(--card); border:3px solid var(--ink); box-shadow:6px 6px 0 var(--ink); margin-bottom:1.2rem; }
.stApp table.tbl { border-collapse:collapse; width:100%; font-size:.9rem; margin:0; }
.stApp table.tbl th { position:sticky; top:0; background:var(--ink) !important; color:var(--pink) !important; font-family:'Anton', sans-serif;
      font-weight:400; text-transform:uppercase; letter-spacing:.03em; text-align:left; padding:.55rem .8rem; white-space:nowrap; border:0; }
.stApp table.tbl td { background:var(--card) !important; color:var(--ink) !important; padding:.5rem .8rem; border:0;
      border-bottom:2px solid #E4DCCB; max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.stApp table.tbl tr:nth-child(even) td { background:#F8EFDB !important; }
.tile { background:var(--card); border:3px solid var(--ink); box-shadow:4px 4px 0 var(--ink); padding:.7rem 1rem; margin-bottom:1.2rem; }
.tile b { display:block; font-family:'Anton', sans-serif; font-weight:400; font-size:2.6rem; line-height:1; color:var(--pink) !important; }
.tile span { color:var(--ink) !important; font-weight:700; }


/* =====================================================================
   SIDEBAR: black panel, light cream text (final override - keep last)
   ===================================================================== */
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { background:var(--ink) !important; }

section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stRadio"] label p,
section[data-testid="stSidebar"] [data-testid="stRadio"] label div { color:#FFF1DC !important; }

section[data-testid="stSidebar"] .me small { color:#E2D2C6 !important; }
section[data-testid="stSidebar"] .brand { color:var(--pink) !important; }
section[data-testid="stSidebar"] .av .face { color:var(--pink) !important; }

/* page you are on turns pink */
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p,
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) div { color:var(--pink) !important; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover p { color:var(--pink) !important; }

/* Log out: outlined in cream, fills pink on hover */
section[data-testid="stSidebar"] .stButton > button,
section[data-testid="stSidebar"] [data-testid^="stBaseButton"] { background:transparent !important; border:3px solid #FFF1DC; box-shadow:3px 3px 0 var(--pink); }
section[data-testid="stSidebar"] .stButton > button p,
section[data-testid="stSidebar"] [data-testid^="stBaseButton"] p { color:#FFF1DC !important; }
section[data-testid="stSidebar"] .stButton > button:hover { background:var(--pink) !important; border-color:#FFF1DC; }
section[data-testid="stSidebar"] .stButton > button:hover p { color:var(--ink) !important; }


/* ---------- post media: standard Instagram feed size (470 px wide, 4:5) ---------- */
[class*="st-key-post_"] [data-testid="stImage"] { width:100% !important; max-width:470px !important;
      margin:0 auto .8rem !important; }
[class*="st-key-post_"] [data-testid="stImage"] img { width:100% !important; height:auto !important; aspect-ratio:470 / 558;
      object-fit:cover; border-radius:12px; border:0; box-shadow:none; display:block; background:#E4DCCB; }
[class*="st-key-post_"] [data-testid="stVideo"], [class*="st-key-post_"] [data-testid="stVideo"] iframe,
[class*="st-key-post_"] [data-testid="stVideo"] video { width:100% !important; max-width:470px; margin:0 auto .8rem;
      display:block; border-radius:12px; }
[class*="st-key-post_"] [data-testid="stVideo"] iframe { aspect-ratio:16 / 9; height:auto !important; border:0; }
[class*="st-key-post_"] [data-testid="stToggle"] { max-width:470px; margin:0 auto .5rem; }
[class*="st-key-post_"] [data-testid="stToggle"] p { font-weight:700; }
.st-key-post_composer { background:var(--pink) !important; }
.st-key-post_composer .phead b { font-size:1.8rem; }
.st-key-post_composer .stFormSubmitButton > button { background:var(--ink) !important; }
.st-key-post_composer .stFormSubmitButton > button p { color:var(--pink) !important; }

/* ---------- delete / unfollow ---------- */
[class*="st-key-delask_"] button { border-color:#E63946; }
[class*="st-key-delyes_"] button { background:#E63946 !important; }
[class*="st-key-row_"] { border-bottom:2px solid var(--ink); padding:.5rem 0; }
"""

st.set_page_config(page_title="Chowk", page_icon="💬", layout="wide")
st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)

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


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"


def media_src(p):
    url = p["photo_url"]
    if url and url.startswith("uploads/"):          # file uploaded from this laptop
        f = BASE_DIR / url
        return str(f) if f.exists() else art(p["post_id"], p["caption"])
    if not url or ("picsum.photos" in url and not picsum_ok()):
        return art(p["post_id"], p["caption"])
    return hd(url)


def video_src(url):
    if url.startswith("uploads/"):
        f = BASE_DIR / url
        return str(f) if f.exists() else None
    return url


def show_video(src):
    """Plays a local file with its proper video type, or a YouTube / .mp4 link."""
    if src.startswith("http"):
        st.video(src)
        return
    fmt = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}.get(Path(src).suffix.lower())
    st.video(src, format=fmt) if fmt else st.video(src)


def ask_delete(pid):
    st.session_state.confirm_delete = pid


def cancel_delete():
    st.session_state.confirm_delete = None


def do_delete(uid, pid):
    for url in db.delete_post(uid, pid):
        if url and url.startswith("uploads/"):
            try:
                (BASE_DIR / url).unlink()
            except FileNotFoundError:
                pass
    st.session_state.confirm_delete = None
    st.toast("Post deleted")


def save_upload(file):
    """Saves an uploaded file into ./uploads and returns (relative path, size in MB)."""
    UPLOAD_DIR.mkdir(exist_ok=True)
    name = secrets.token_hex(8) + Path(file.name).suffix.lower()
    (UPLOAD_DIR / name).write_bytes(file.getbuffer())
    return "uploads/" + name, round(file.size / 1048576, 2)


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
        st.image(media_src(p))
        if p["video_url"]:
            if p["video_url"].startswith("uploads/") or st.toggle("Watch video", key="vid_" + ctx + "_" + str(pid)):
                src = video_src(p["video_url"])
                if src:
                    show_video(src)
                else:
                    st.warning("This video file is missing from the uploads folder.")
        st.markdown('<div class="caption">' + esc(p["caption"]) + "</div>", unsafe_allow_html=True)
        if p["tags"]:
            st.markdown('<div class="tags">' + "".join("<span>" + esc(t) + "</span>" for t in p["tags"].split())
                        + "</div>", unsafe_allow_html=True)

        cols = st.columns([1, 1, 1, 3] if ctx == "mine" else [1, 1, 4])
        a, b = cols[0], cols[1]
        a.button(("♥ " if liked else "♡ ") + str(p["likes"]),
                 key="like" + ("on" if liked else "off") + "_" + ctx + "_" + str(pid),
                 on_click=db.toggle_like, args=(uid, pid))
        b.button("Saved" if saved else "Save",
                 key="save" + ("on" if saved else "off") + "_" + ctx + "_" + str(pid),
                 on_click=db.toggle_bookmark, args=(uid, pid))

        if ctx == "mine":
            cols[2].button("Delete", key="delask_" + ctx + "_" + str(pid), on_click=ask_delete, args=(pid,))
            if st.session_state.get("confirm_delete") == pid:
                st.warning("Delete this post with its photo, video, likes and comments? This cannot be undone.")
                y, n, _ = st.columns([1, 1, 4])
                y.button("Yes, delete", key="delyes_" + str(pid), on_click=do_delete, args=(uid, pid))
                n.button("Cancel", key="delno_" + str(pid), on_click=cancel_delete)

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
    banner("New post", "Share a photo, a video, or both")
    with st.container(key="post_composer"):
        st.markdown('<div class="phead"><b>Share a moment</b></div>', unsafe_allow_html=True)
        with st.form("new_post", clear_on_submit=True):
            caption = st.text_area("Caption", max_chars=200, placeholder="What did you see today? Add #hashtags")
            location = st.text_input("Location (optional)", max_chars=50)
            c1, c2 = st.columns(2)
            st.caption("After choosing a file, wait until its name and size appear before pressing Post. "
                       "Use .mp4 videos for best results (.mov only plays in Safari).")
            photo_file = c1.file_uploader("Photo from your computer (under 5 MB)", type=["jpg", "jpeg", "png", "webp"])
            photo_link = c1.text_input("...or a photo link")
            video_file = c2.file_uploader("Video from your computer (under 10 MB)", type=["mp4", "mov", "webm"])
            video_link = c2.text_input("...or a video link (YouTube or .mp4)")
            sent = st.form_submit_button("Post")
        if sent:
            photo_url, video_url = photo_link.strip(), video_link.strip()
            if not caption.strip():
                st.warning("Write a caption first.")
            elif photo_file is not None and photo_file.size >= 5 * 1048576:
                st.error("Photos must be under 5 MB.")
            elif video_file is not None and video_file.size >= 10 * 1048576:
                st.error("Videos must be under 10 MB.")
            elif (photo_url and not photo_url.startswith("http")) or (video_url and not video_url.startswith("http")):
                st.error("Links must start with http:// or https://")
            else:
                photo_mb = video_mb = None
                if photo_file is not None:
                    photo_url, photo_mb = save_upload(photo_file)
                if video_file is not None:
                    video_url, video_mb = save_upload(video_file)
                try:
                    db.create_post(me["user_id"], caption.strip(), location.strip(),
                                   photo_url or None, video_url or None, photo_mb, video_mb)
                    got = []
                    if photo_url:
                        got.append("photo (" + ("uploaded" if photo_file is not None else "link") + ")")
                    if video_url:
                        got.append("video (" + ("uploaded" if video_file is not None else "link") + ")")
                    if got:
                        st.success("Posted with " + " and ".join(got) + ". Open Feed to see it.")
                        if video_file is not None:
                            st.caption("Preview of the video you just uploaded:")
                            show_video(str(BASE_DIR / video_url))
                    else:
                        st.warning("Posted as text only: no photo or video was attached, so Feed shows a poster made "
                                   "from your caption. Pick a file and wait until it finishes uploading (or paste "
                                   "a link), then post again.")
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
    with t_fers:
        people = db.get_connections(me["user_id"], "followers")
        st.markdown("".join('<span class="chip">' + esc(r["username"]) + "</span>" for r in people)
                    or "Nobody follows you yet.", unsafe_allow_html=True)
    with t_fing:
        people = db.get_connections(me["user_id"], "following")
        if not people:
            st.markdown("You aren't following anyone yet. Find people on the People page.")
        for r in people:
            with st.container(key="row_" + str(r["user_id"])):
                left, right = st.columns([4, 1])
                left.markdown('<div class="phead" style="margin:0">' + avatar(r["profile_photo_url"], r["username"], 40)
                              + "<div><b>" + esc(r["username"]) + "</b></div></div>", unsafe_allow_html=True)
                right.button("Unfollow", key="unfol_" + str(r["user_id"]),
                             on_click=db.unfollow, args=(me["user_id"], r["user_id"]))


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