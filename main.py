import os
import math
import re
import colorsys
import unicodedata
import pandas as pd
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all_tables
from zoneinfo import ZoneInfo  # stdlib tz, no extra dependency
from datetime import datetime

import nltk
from nltk.data import find
from nltk.corpus import wordnet
from nltk.stem import WordNetLemmatizer

from wordcloud import WordCloud


# -------------------------------
# State / Globals
# -------------------------------
error_message = ""

account_data = pd.DataFrame(columns=["Date", "Reach", "Lifetime Follower Count"])
posts_data = pd.DataFrame(columns=["Post ID", "Likes Count", "Reach", "Saves", "Timestamp"])

selected_post = ""
post_options = []

post_likes = 0
post_reach = 0
post_saves = 0
post_comments = 0
post_engagement = 0.0

current_followers = 0
latest_reach = 0
profile_views = 0
total_posts = 0
total_likes = 0

# Aggregation controls
agg_granularity = "Day"  # Day | Week
date_start = ""          # YYYY-MM-DD
date_end = ""            # YYYY-MM-DD
agg_engagement_over_time = pd.DataFrame(columns=["Date", "Engagement Rate"])

APP_TZ = ZoneInfo("America/Sao_Paulo")  # display timezone
last_updated_str = "—"

is_refreshing = False
refresh_status = ""

# -------------------------------
# Semantics / Hook word cloud state
# -------------------------------
hook_metric = "Likes"
hook_metric_lov = [
    "Likes",
    "Audience Comments",
    "Likes + Audience Comments",
    "Average Watch Time",
]

hook_wordcloud_path = ""  # generated PNG
hook_top_words = pd.DataFrame(columns=["word", "freq", "metric_avg"])


# -------------------------------
# Helpers
# -------------------------------
def nz(x, default=0):
    """Return default for None/NaN; otherwise x."""
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return x
    except Exception:
        return default


# -------------------------------
# Semantics helpers (emoji stripping + EN lemmatization + custom remove list)
# -------------------------------
def _ensure_nltk():
    # wordnet for English lemmatization
    try:
        find("corpora/wordnet")
    except LookupError:
        nltk.download("wordnet", quiet=True)

    # wordnet multi-lingual index (often used by wordnet)
    try:
        find("corpora/omw-1.4")
    except LookupError:
        nltk.download("omw-1.4", quiet=True)

    # POS tagger for better lemmatization
    try:
        find("taggers/averaged_perceptron_tagger")
    except LookupError:
        nltk.download("averaged_perceptron_tagger", quiet=True)

_ensure_nltk()
_LEMMATIZER = WordNetLemmatizer()

# REMOVE: articles, most prepositions, generic linking/filler
REMOVE_WORDS = set([
    # Portuguese articles/determiners
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "ao", "aos", "à", "às", "da", "das", "do", "dos",
    "no", "na", "nos", "nas",
    "num", "numa", "nuns", "numas",

    # Portuguese prepositions (most)
    "de", "em", "para", "pra", "com", "por", "sem", "sobre", "entre", "até",
    "contra", "desde", "perante", "após", "antes", "durante",

    # Generic linking/filler
    "e", "ou", "mas", "porém", "pois", "então", "daí", "assim", "tipo", "né", "eh", "aí", "ai",

    # English articles/prepositions/linkers
    "the", "a", "an",
    "to", "of", "in", "on", "for", "with", "from", "by", "at", "into", "onto", "over", "under",
    "between", "through", "during", "before", "after", "without", "against", "about", "around",
    "and", "or", "but", "so", "then",
])

# KEEP: pronouns + question words + hook-critical
KEEP_WORDS = set([
    # Portuguese pronouns/direct address
    "você", "vocês", "vc", "vcs", "eu", "nós",

    # Portuguese question words / forms
    "como", "quando", "onde", "qual", "quais", "quem", "que", "quê",
    "por_que", "o_que", "pra_que", "para_que",

    # English pronouns/question words
    "you", "your", "i", "we", "my", "me", "our",
    "why", "how", "what", "when", "where", "which", "who",
])

QUESTION_PHRASES = {
    ("por", "que"): "por_que",
    ("o", "que"): "o_que",
    ("pra", "que"): "pra_que",
    ("para", "que"): "para_que",
}

def _strip_emojis(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    out = []
    for ch in text:
        cp = ord(ch)
        if (
            0x1F300 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x26FF
            or 0x2700 <= cp <= 0x27BF
            or 0xFE00 <= cp <= 0xFE0F
            or 0x1F1E6 <= cp <= 0x1F1FF
            or cp == 0x200D
        ):
            continue
        if unicodedata.category(ch) == "So":
            continue
        out.append(ch)
    return "".join(out)

def _nltk_pos_to_wordnet(tag: str):
    if not tag:
        return wordnet.NOUN
    if tag.startswith("V"):
        return wordnet.VERB
    if tag.startswith("J"):
        return wordnet.ADJ
    if tag.startswith("R"):
        return wordnet.ADV
    return wordnet.NOUN

def _fold_question_phrases(tokens):
    out = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            pair = (tokens[i], tokens[i + 1])
            if pair in QUESTION_PHRASES:
                out.append(QUESTION_PHRASES[pair])
                i += 2
                continue
        out.append(tokens[i])
        i += 1
    return out

def _should_remove(tok: str) -> bool:
    if tok in KEEP_WORDS:
        return False
    return tok in REMOVE_WORDS

def _is_mostly_ascii(token: str) -> bool:
    if not token:
        return True
    ascii_count = sum(1 for c in token if ord(c) < 128)
    return (ascii_count / max(1, len(token))) >= 0.9

def _tokenize_hook_text(text: str):
    if not isinstance(text, str):
        return []

    text = _strip_emojis(text).strip().lower()
    if not text:
        return []

    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    raw_tokens = re.findall(r"[a-zà-öø-ÿ']+", text, flags=re.IGNORECASE)

    tokens = []
    for t in raw_tokens:
        t = t.strip("'")
        if len(t) < 2:
            continue
        tokens.append(t)

    if not tokens:
        return []

    tokens = _fold_question_phrases(tokens)

    try:
        tagged = nltk.pos_tag(tokens)
    except Exception:
        tagged = [(t, "") for t in tokens]

    out = []
    for tok, pos in tagged:
        if tok in QUESTION_PHRASES.values():
            out.append(tok)
            continue

        if _should_remove(tok):
            continue

        norm = tok
        # Only English lemmatization; PT kept as-is
        if _is_mostly_ascii(tok):
            norm = _LEMMATIZER.lemmatize(tok, _nltk_pos_to_wordnet(pos))

        if len(norm) < 2:
            continue
        out.append(norm)

    return out


# -------------------------------
# Engagement mapping (for dropdown)
# -------------------------------
def _get_metric_value(row, metric_name: str) -> float:
    likes = float(nz(row.get("Likes Count", 0), 0) or 0)
    aud = float(nz(row.get("Audience Comments Count", 0), 0) or 0)
    awt = float(nz(row.get("Average Watch Time", 0), 0) or 0)

    if metric_name == "Likes":
        return likes
    if metric_name == "Audience Comments":
        return aud
    if metric_name == "Likes + Audience Comments":
        return likes + aud
    if metric_name == "Average Watch Time":
        return awt
    return likes


# -------------------------------
# Hook stats builder (required by generate_hook_wordcloud)
# -------------------------------
def _build_hook_word_stats(df: pd.DataFrame, metric_name: str) -> pd.DataFrame:
    """
    Returns dataframe: word, freq, metric_avg

    freq:
      Token frequency across hooks (counts repeated occurrences within a hook).
    metric_avg:
      Average engagement metric across posts that contain the word
      (counts a word at most once per post for the average).
    """
    if df.empty:
        return pd.DataFrame(columns=["word", "freq", "metric_avg"])

    freq = {}
    metric_sum = {}
    metric_cnt = {}

    for _, row in df.iterrows():
        tokens = _tokenize_hook_text(row.get("Hook Text", ""))
        if not tokens:
            continue

        # frequency counts (each occurrence)
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1

        mval = _get_metric_value(row, metric_name)

        # metric averages (unique per post)
        for t in set(tokens):
            metric_sum[t] = metric_sum.get(t, 0.0) + float(mval)
            metric_cnt[t] = metric_cnt.get(t, 0) + 1

    rows = []
    for w, f in freq.items():
        cnt = metric_cnt.get(w, 0)
        avg = (metric_sum.get(w, 0.0) / cnt) if cnt else 0.0
        rows.append((w, int(f), float(avg)))

    out = pd.DataFrame(rows, columns=["word", "freq", "metric_avg"])
    # Keep the existing sort for other uses; table sort is handled separately.
    out = out.sort_values(["freq", "metric_avg"], ascending=[False, False]).reset_index(drop=True)
    return out


# -------------------------------
# Word cloud generation
# SIZE BY engagement metric, COLOR BY frequency
# -------------------------------
def _warm_cool_rgb(norm01: float) -> str:
    x = max(0.0, min(1.0, float(norm01)))
    hue = (240.0 - 220.0 * x) / 360.0  # blue -> orange/red
    r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
    return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

def generate_hook_wordcloud(metric_name: str, state=None):
    global hook_wordcloud_path, hook_top_words, posts_data

    if posts_data is None or posts_data.empty:
        hook_wordcloud_path = ""
        hook_top_words = pd.DataFrame(columns=["word", "freq", "metric_avg"])
        if state:
            state.hook_wordcloud_path = hook_wordcloud_path
            state.hook_top_words = hook_top_words
        return

    df = posts_data.copy()

    # Only VIDEO + non-empty Hook Text
    if "Content Type" in df.columns:
        df = df[df["Content Type"].astype(str).str.upper() == "VIDEO"]
    if "Hook Text" in df.columns:
        df = df[df["Hook Text"].astype(str).str.strip().ne("")]
    else:
        df = df.iloc[0:0]

    stats = _build_hook_word_stats(df, metric_name)

    # Top hook words table: top 5 by the selected engagement metric (metric_avg)
    hook_top_words = stats.sort_values("metric_avg", ascending=False).head(5).copy()

    if stats.empty:
        hook_wordcloud_path = ""
        if state:
            state.hook_wordcloud_path = hook_wordcloud_path
            state.hook_top_words = hook_top_words
        return

    # SIZE: engagement weights
    metric_map = dict(zip(stats["word"], stats["metric_avg"]))
    size_weights = {w: math.log1p(max(0.0, float(v))) for w, v in metric_map.items()}

    # COLOR: frequency
    freq_map = dict(zip(stats["word"], stats["freq"]))
    fmin = float(stats["freq"].min())
    fmax = float(stats["freq"].max())
    fden = (fmax - fmin) if (fmax - fmin) != 0 else 1.0

    def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
        f = float(freq_map.get(word, fmin))
        norm = (f - fmin) / fden
        return _warm_cool_rgb(norm)

    wc = WordCloud(
        width=1400,
        height=700,
        background_color="white",
        collocations=False,
        prefer_horizontal=0.95,
    ).generate_from_frequencies(size_weights)

    wc = wc.recolor(color_func=color_func)

    out_path = os.path.join(os.getcwd(), "hook_wordcloud.png")
    wc.to_file(out_path)

    hook_wordcloud_path = "hook_wordcloud.png"

    if state:
        state.hook_wordcloud_path = hook_wordcloud_path
        state.hook_top_words = hook_top_words


def update_hook_wordcloud(state):
    global hook_metric
    hook_metric = state.hook_metric
    generate_hook_wordcloud(hook_metric, state=state)


# -------------------------------
# Engagement / Post metrics helpers
# -------------------------------
def calculate_engagement_rate(row):
    try:
        audience_comments = float(nz(row.get("Audience Comments Count", 0)))
        likes = float(nz(row.get("Likes Count", 0)))
        saves = float(nz(row.get("Saves", 0)))
        reach = float(nz(row.get("Reach", 0)))
        if reach > 0:
            return round(((audience_comments + likes + saves) / reach) * 100, 2)
        return 0.0
    except Exception:
        return 0.0

def get_post_metrics(post_id):
    if posts_data.empty or str(post_id) not in posts_data.get("Post ID", []).astype(str).tolist():
        return 0, 0, 0, 0, 0.0
    row = posts_data[posts_data["Post ID"].astype(str) == str(post_id)].iloc[0]
    return (
        int(nz(row.get("Likes Count", 0))),
        int(nz(row.get("Reach", 0))),
        int(nz(row.get("Saves", 0))),
        int(nz(row.get("Audience Comments Count", 0))),
        float(nz(row.get("Engagement Rate", 0.0))),
    )

def _parse_date(s):
    try:
        return pd.to_datetime(s).date() if s else None
    except Exception:
        return None

def recompute_agg(state=None):
    global agg_engagement_over_time
    df = posts_data.copy()
    agg_engagement_over_time = pd.DataFrame(columns=["Date", "Engagement Rate"])

    if df.empty or "Timestamp" not in df.columns:
        if state is not None:
            state.agg_engagement_over_time = agg_engagement_over_time
        return

    df["__dt"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["__dt"])

    _start = _parse_date(state.date_start if state is not None else date_start)
    _end = _parse_date(state.date_end if state is not None else date_end)
    if _start:
        df = df[df["__dt"].dt.date >= _start]
    if _end:
        df = df[df["__dt"].dt.date <= _end]

    gran = (state.agg_granularity if state is not None else agg_granularity) or "Day"
    if gran == "Week":
        key = df["__dt"].dt.to_period("W").apply(lambda p: p.start_time.date())
    else:
        key = df["__dt"].dt.date

    group = df.groupby(key).agg(
        {
            "Likes Count": "sum",
            "Audience Comments Count": "sum",
            "Saves": "sum",
            "Reach": "sum",
        }
    ).reset_index()
    group = group.rename(columns={group.columns[0]: "Date"})

    if len(group) > 0:
        group["Engagement Rate"] = (
            (group.get("Likes Count", 0) + group.get("Audience Comments Count", 0) + group.get("Saves", 0))
            / group.get("Reach", 0).replace(0, pd.NA)
        ) * 100
        group["Engagement Rate"] = group["Engagement Rate"].fillna(0).round(2)
        agg_engagement_over_time = group[["Date", "Engagement Rate"]]

    if state is not None:
        state.agg_engagement_over_time = agg_engagement_over_time

def _on_agg_change(state):
    recompute_agg(state)

def fmt_int(n):
    try:
        return f"{int(n):,}"
    except Exception:
        return "0"

def refresh_formats():
    global current_followers_fmt, latest_reach_fmt, profile_views_fmt
    global post_likes_fmt, post_reach_fmt, post_saves_fmt, post_comments_fmt
    global total_likes_fmt
    current_followers_fmt = fmt_int(current_followers)
    latest_reach_fmt = fmt_int(latest_reach)
    profile_views_fmt = fmt_int(profile_views)
    post_likes_fmt = fmt_int(post_likes)
    post_reach_fmt = fmt_int(post_reach)
    post_saves_fmt = fmt_int(post_saves)
    post_comments_fmt = fmt_int(post_comments)
    total_likes_fmt = fmt_int(total_likes)

def _latest_updated_at_str():
    def _pick_col(df):
        if df is None or df.empty:
            return None
        for name in ("Updated At", "Updated_at", "updated_at"):
            if name in df.columns:
                return name
        return None

    candidates = []
    for df in (account_data, posts_data):
        col = _pick_col(df)
        if col:
            s = pd.to_datetime(df[col], errors="coerce", utc=True)
            s = s.dropna()
            if not s.empty:
                candidates.append(s.max())

    if not candidates:
        return "—"

    latest = max(candidates).tz_convert(APP_TZ)
    return latest.strftime("%Y-%m-%d %H:%M %Z")


def reload_data(state=None):
    global account_data, posts_data, total_posts, total_likes
    global current_followers, latest_reach, profile_views
    global post_options, selected_post, last_updated_str
    global post_likes, post_reach, post_saves, post_comments, post_engagement
    global is_refreshing, refresh_status

    is_refreshing = True
    refresh_status = "Refreshing…"
    if state:
        state.is_refreshing = True
        state.refresh_status = refresh_status

    try:
        cfg = get_airtable_config()
        all_data = fetch_all_tables(cfg["api_key"], cfg["base_id"], cfg["tables"])

        # Account metrics
        account_data = all_data.get("ig_accounts", pd.DataFrame())
        if not account_data.empty and "Date" in account_data.columns:
            account_data["Date"] = pd.to_datetime(account_data["Date"], errors="coerce")
            account_data = account_data.sort_values("Date")
            account_data["Day"] = account_data["Date"].dt.day_name()

            if len(account_data) > 0:
                last = account_data.iloc[-1]
                current_followers = int(nz(last.get("Lifetime Follower Count", 0)))
                latest_reach = int(nz(last.get("Reach", 0)))
                profile_views = int(nz(last.get("Lifetime Profile Views", 0)))

        # Posts
        posts_data = all_data.get("ig_posts", pd.DataFrame())
        if not posts_data.empty:
            if "Timestamp" in posts_data.columns:
                posts_data["Timestamp"] = pd.to_datetime(posts_data["Timestamp"], errors="coerce")
                posts_data = posts_data.sort_values("Timestamp", ascending=False)

            if "Post ID" in posts_data.columns:
                posts_data["Post ID"] = posts_data["Post ID"].astype(str)

            posts_data["Engagement Rate"] = posts_data.apply(calculate_engagement_rate, axis=1)

            total_posts = len(posts_data)
            if "Likes Count" in posts_data.columns:
                total_likes = int(pd.to_numeric(posts_data["Likes Count"], errors="coerce").fillna(0).sum())

            # init date window
            try:
                if "Timestamp" in posts_data.columns and len(posts_data) > 0:
                    _dt = pd.to_datetime(posts_data["Timestamp"], errors="coerce").dropna()
                    if _dt is not None and len(_dt) > 0:
                        if state is None or not getattr(state, "date_start", ""):
                            globals()["date_start"] = str(_dt.min().date())
                        if state is None or not getattr(state, "date_end", ""):
                            globals()["date_end"] = str(_dt.max().date())
            except Exception as _e:
                print("Date range init error (reload):", _e)

            if "Display Label" not in posts_data.columns:
                posts_data["Display Label"] = posts_data.apply(
                    lambda r: f"{r.get('Content Type','POST')}: "
                              f"{r['Timestamp'].strftime('%b %d, %Y') if pd.notna(r.get('Timestamp')) else 'No Date'}",
                    axis=1
                )

            post_options = list(zip(posts_data["Post ID"].astype(str).tolist(),
                                    posts_data["Display Label"].tolist()))

            if state:
                current_sel = getattr(state, "selected_post", "")
                if current_sel not in posts_data["Post ID"].astype(str).tolist():
                    state.selected_post = str(posts_data["Post ID"].iloc[0]) if len(posts_data) else ""
                update_post_metrics(state)
            else:
                if selected_post not in posts_data["Post ID"].astype(str).tolist():
                    selected_post = str(posts_data["Post ID"].iloc[0]) if len(posts_data) else ""
                (post_likes, post_reach, post_saves,
                 post_comments, post_engagement) = get_post_metrics(selected_post)

        if state:
            recompute_agg(state)
        else:
            recompute_agg()

        refresh_formats()

        # Semantics
        if state:
            if not hasattr(state, "hook_metric") or not state.hook_metric:
                state.hook_metric = hook_metric
            generate_hook_wordcloud(state.hook_metric, state=state)
        else:
            generate_hook_wordcloud(hook_metric)

        last_updated_str = _latest_updated_at_str()
        if state:
            state.last_updated_str = last_updated_str

    except Exception as e:
        print("Reload error:", e)

    finally:
        is_refreshing = False
        refresh_status = ""
        if state:
            state.is_refreshing = False
            state.refresh_status = refresh_status


# -------------------------------
# Initial data load
# -------------------------------
try:
    cfg = get_airtable_config()
    API_KEY = cfg["api_key"]
    BASE_ID = cfg["base_id"]

    all_data = fetch_all_tables(API_KEY, BASE_ID, cfg["tables"])

    # Account metrics
    account_data = all_data.get("ig_accounts", pd.DataFrame())
    if not account_data.empty and "Date" in account_data.columns:
        account_data["Date"] = pd.to_datetime(account_data["Date"], errors="coerce")
        account_data = account_data.sort_values("Date")
        account_data["Day"] = account_data["Date"].dt.day_name()

        if len(account_data) > 0:
            latest_row = account_data.iloc[-1]
            current_followers = int(nz(latest_row.get("Lifetime Follower Count", 0)))
            latest_reach = int(nz(latest_row.get("Reach", 0)))
            profile_views = int(nz(latest_row.get("Lifetime Profile Views", 0)))

    # Posts
    posts_data = all_data.get("ig_posts", pd.DataFrame())
    if not posts_data.empty:
        if "Timestamp" in posts_data.columns:
            posts_data["Timestamp"] = pd.to_datetime(posts_data["Timestamp"], errors="coerce")
            posts_data = posts_data.sort_values("Timestamp", ascending=False)

        if "Post ID" in posts_data.columns:
            posts_data["Post ID"] = posts_data["Post ID"].astype(str)

        posts_data["Engagement Rate"] = posts_data.apply(calculate_engagement_rate, axis=1)

        total_posts = len(posts_data)
        if "Likes Count" in posts_data.columns:
            total_likes = int(pd.to_numeric(posts_data["Likes Count"], errors="coerce").fillna(0).sum())

        try:
            if "Timestamp" in posts_data.columns and len(posts_data) > 0:
                _dt = pd.to_datetime(posts_data["Timestamp"], errors="coerce").dropna()
                if _dt is not None and len(_dt) > 0:
                    date_start = str(_dt.min().date())
                    date_end = str(_dt.max().date())
        except Exception as _e:
            print("Date range init error:", _e)

        if "Display Label" not in posts_data.columns:
            posts_data["Display Label"] = posts_data.apply(
                lambda row: f"{row.get('Content Type', 'POST')}: "
                            f"{row['Timestamp'].strftime('%b %d, %Y') if pd.notna(row.get('Timestamp')) else 'No Date'}",
                    axis=1
                )

        if "Post ID" in posts_data.columns:
            post_options = list(zip(posts_data["Post ID"].astype(str).tolist(),
                                    posts_data["Display Label"].tolist()))
            selected_post = str(posts_data["Post ID"].iloc[0]) if len(posts_data) > 0 else ""
            if selected_post:
                (post_likes, post_reach, post_saves,
                 post_comments, post_engagement) = get_post_metrics(selected_post)

        recompute_agg()
        refresh_formats()

        # Initial Semantics build so the tab isn't empty on first load
        generate_hook_wordcloud(hook_metric)

except Exception as e:
    error_message = f"⚠️ {e}"
    print(f"✗ Error: {e}")

last_updated_str = _latest_updated_at_str()


def update_post_metrics(state):
    (state.post_likes,
     state.post_reach,
     state.post_saves,
     state.post_comments,
     state.post_engagement) = get_post_metrics(state.selected_post)

    global post_likes, post_reach, post_saves, post_comments, post_engagement
    post_likes = state.post_likes
    post_reach = state.post_reach
    post_saves = state.post_saves
    post_comments = state.post_comments
    post_engagement = state.post_engagement

    state.post_likes_fmt = fmt_int(state.post_likes)
    state.post_reach_fmt = fmt_int(state.post_reach)
    state.post_saves_fmt = fmt_int(state.post_saves)
    state.post_comments_fmt = fmt_int(state.post_comments)

    refresh_formats()


# -------------------------------
# UI
# -------------------------------
root_page = """<|layout|columns=250px 1fr|
<|part|class_name=sidebar|
<|logo.png|image|width=120px|>

# 📊 Malugo Analytics

## Dashboards

[📈 Engagement](Engagement_Dashboard)

[🎬 Post Performance](Post_Performance)

[⚙️ Content Efficiency](Content_Efficiency)

[💬 Semantics & Sentiment](Semantics_Sentiment)
|>

<|part|class_name=content|
<|content|>
|>
|>
"""

engagement_dashboard_layout = """# 📊 Account Engagement Overview

<|layout|columns=auto auto auto|gap=24px|class_name=inline-controls|
<|**Updated at (America/Sao_Paulo):** {last_updated_str}|text|class_name=inline-text|>
<|Refresh data|button|class_name=btn-refresh|on_action=reload_data|>
<|{refresh_status}|text|class_name=muted|>
|>

<|layout|columns=1 1 1|gap=20px|class_name=metrics-grid|

<|
## 👥 Current Followers
<|{current_followers_fmt}|text|class_name=metric-number|>
|>

<|
## 📈 Latest Reach
<|{latest_reach_fmt}|text|class_name=metric-number|>
|>

<|
## 👁️ Profile Views (Yesterday)
<|{profile_views_fmt}|text|class_name=metric-number|>
|>

|>

---
## 📊 Growth Trends

<|{account_data}|chart|type=line|x=Date|y[1]=Reach|y[2]=Lifetime Follower Count|title=Reach & Follower Growth|class_name=narrow|>

<|{account_data}|chart|type=bar|x=Day|y=Reach|title=Reach by Day of Week|class_name=narrow|>

<|part|class_name=panel|
## 📈 Total Engagement Rate Over Time (All Posts)
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*

<|layout|columns=1 1 1|gap=10px|
**Group by**
<|{agg_granularity}|selector|lov=Day;Week|dropdown|on_change=_on_agg_change|>
**Start date**
<|{date_start}|date|on_change=_on_agg_change|>
**End date**
<|{date_end}|date|on_change=_on_agg_change|>
|>

<|{agg_engagement_over_time}|chart|type=line|x=Date|y=Engagement Rate|title=Total Engagement Rate Over Time|class_name=narrow|>
|>
"""

post_performance_layout = """# 🎬 Post Performance Analysis

<|layout|columns=auto auto auto|gap=24px|class_name=inline-controls|
<|**Updated at (America/Sao_Paulo):** {last_updated_str}|text|class_name=inline-text|>
<|Refresh data|button|class_name=btn-refresh|on_action=reload_data|>
<|{refresh_status}|text|class_name=muted|>
|>

<|layout|columns=1 1|gap=20px|class_name=metrics-grid|

<|
## 📊 Total Posts
<|{total_posts}|text|class_name=metric-number|>
|>

<|
## 💖 Total Likes
<|{total_likes_fmt}|text|class_name=metric-number|>
|>

|>

---
## 🔍 Individual Post Analysis
**Select a Post:**
<|{selected_post}|selector|lov={post_options}|dropdown|value_by_id=True|on_change=update_post_metrics|>

<|layout|columns=1 1 1|gap=15px|class_name=metrics-grid|

<|
**Likes**  
<|{post_likes_fmt}|text|class_name=metric-number|>
|>

<|
**Reach**  
<|{post_reach_fmt}|text|class_name=metric-number|>
|>

<|
**Saves**  
<|{post_saves_fmt}|text|class_name=metric-number|>
|>

|>

<|layout|columns=1 1|gap=15px|class_name=metrics-grid|

<|
**Audience Comments**  
<|{post_comments_fmt}|text|class_name=metric-number|>
|>

<|
**Engagement Rate**  
<|{post_engagement}|text|format=%.2f|class_name=metric-number|>%
|>

|>

---
## 📈 Performance Trends
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*
<|{posts_data}|chart|type=scatter|mode=lines+markers|x=Timestamp|y=Engagement Rate|title=Engagement Rate Over Time|class_name=narrow|>

---
## 🏆 Top 5 Performers
*Engagement Rate = (Audience Comments + Likes + Saves) / Reach × 100*
<|{posts_data.nlargest(5, 'Engagement Rate')[['Display Label', 'Likes Count', 'Reach', 'Saves', 'Audience Comments Count', 'Engagement Rate']] if 'Engagement Rate' in posts_data.columns else pd.DataFrame()}|table|>
"""

content_efficiency_layout = """# ⚙️ Content Efficiency Dashboard

Coming soon!
"""

semantics_layout = """# 💬 Semantics: Hook Word Cloud (Engagement-Weighted)

Words are coloured by frequency of appearance in hooks across videos (warmer tones for higher frequency).

Size words by:

<|{hook_metric}|selector|lov={hook_metric_lov}|dropdown|on_change=update_hook_wordcloud|>

<|layout|columns=5 3|gap=20px|
<|{hook_wordcloud_path}|image|width=100%|>
<||>
|>

---

## 🔎 Top hook words
<|{hook_top_words}|table|page_size=5|>
"""


pages = {
    "/": root_page,
    "Engagement_Dashboard": engagement_dashboard_layout,
    "Post_Performance": post_performance_layout,
    "Content_Efficiency": content_efficiency_layout,
    "Semantics_Sentiment": semantics_layout,
}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app = Gui(pages=pages, css_file="style.css")

    app.run(
        title="Malugo Analytics ✨",
        host="0.0.0.0",
        port=port,
        dark_mode=True,
    )
