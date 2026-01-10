import os
import math
import re
import colorsys
import unicodedata
import pandas as pd
from taipy.gui import Gui
from data.config_loader import get_airtable_config
from data.airtable_fetch import fetch_all_tables
from zoneinfo import ZoneInfo
from datetime import datetime

import nltk
from nltk.data import find
from nltk.corpus import wordnet
from nltk.stem import WordNetLemmatizer

from wordcloud import WordCloud


# -------------------------------
# Globals / State
# -------------------------------
error_message = ""

account_data = pd.DataFrame()
posts_data = pd.DataFrame()

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

agg_granularity = "Day"
date_start = ""
date_end = ""
agg_engagement_over_time = pd.DataFrame(columns=["Date", "Engagement Rate"])

APP_TZ = ZoneInfo("America/Sao_Paulo")
last_updated_str = "—"

is_refreshing = False
refresh_status = ""

# -------------------------------
# Semantics state
# -------------------------------
hook_metric = "Likes"
hook_metric_lov = "Likes;Audience Comments;Likes + Audience Comments;Average Watch Time"
hook_wordcloud_path = ""
hook_top_words = pd.DataFrame(columns=["word", "engagement_weight"])


# -------------------------------
# Helpers
# -------------------------------
def nz(x, default=0):
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return x
    except Exception:
        return default


# -------------------------------
# NLP setup
# -------------------------------
def _ensure_nltk():
    for res in [
        ("corpora/wordnet", "wordnet"),
        ("corpora/omw-1.4", "omw-1.4"),
        ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
    ]:
        try:
            find(res[0])
        except LookupError:
            nltk.download(res[1], quiet=True)


_ensure_nltk()
_LEMMATIZER = WordNetLemmatizer()

# REMOVE: articles, most prepositions, generic linking/filler
# KEEP: pronouns, question words, etc. (via KEEP_WORDS)
REMOVE_WORDS = {
    # PT articles/determiners
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "ao", "aos", "à", "às", "da", "das", "do", "dos",
    "no", "na", "nos", "nas",
    "num", "numa", "nuns", "numas",

    # PT prepositions
    "de", "em", "para", "pra", "com", "por", "sem", "sobre", "entre", "até",
    "contra", "desde", "perante", "após", "antes", "durante",

    # PT linkers/fillers
    "e", "ou", "mas", "porém", "pois", "então", "daí", "assim", "tipo", "né", "eh", "aí", "ai",

    # EN articles/prepositions/linkers
    "the", "a", "an",
    "to", "of", "in", "on", "for", "with", "from", "by", "at", "into", "onto", "over", "under",
    "between", "through", "during", "before", "after", "without", "against", "about", "around",
    "and", "or", "but", "so", "then",
}

# Explicit KEEP list (not exhaustive; just overrides removal)
KEEP_WORDS = {
    # PT pronouns/direct address
    "você", "vocês", "vc", "vcs", "eu", "nós",

    # PT question words / forms
    "como", "quando", "onde", "qual", "quais", "quem", "que", "quê",
    "por_que", "o_que", "pra_que", "para_que",

    # EN pronouns/question words
    "you", "your", "i", "we", "my", "me", "our",
    "why", "how", "what", "when", "where", "which", "who",
}

QUESTION_PHRASES = {
    ("por", "que"): "por_que",
    ("o", "que"): "o_que",
    ("pra", "que"): "pra_que",
    ("para", "que"): "para_que",
}


def _strip_emojis(text):
    if not isinstance(text, str):
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


def _nltk_pos_to_wordnet(tag):
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


def _tokenize_hook_text(text):
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

        # English lemmatization only; PT left as-is to preserve pronouns etc.
        norm = tok
        if _is_mostly_ascii(tok):
            norm = _LEMMATIZER.lemmatize(tok, _nltk_pos_to_wordnet(pos))

        if len(norm) < 2:
            continue

        out.append(norm)

    return out


# -------------------------------
# Engagement mapping
# -------------------------------
def _get_metric_value(row, metric):
    likes = float(nz(row.get("Likes Count", 0)))
    comments = float(nz(row.get("Audience Comments Count", 0)))
    awt = float(nz(row.get("Average Watch Time", 0)))

    if metric == "Likes":
        return likes
    if metric == "Audience Comments":
        return comments
    if metric == "Likes + Audience Comments":
        return likes + comments
    if metric == "Average Watch Time":
        return awt
    return likes


# -------------------------------
# Word cloud generation (size by engagement, color by engagement)
# -------------------------------
def generate_hook_wordcloud(metric, state=None):
    global hook_wordcloud_path, hook_top_words, posts_data

    if posts_data is None or posts_data.empty:
        hook_wordcloud_path = ""
        hook_top_words = pd.DataFrame(columns=["word", "engagement_weight"])
        if state:
            state.hook_wordcloud_path = hook_wordcloud_path
            state.hook_top_words = hook_top_words
        return

    df = posts_data.copy()

    if "Content Type" in df.columns:
        df = df[df["Content Type"].astype(str).str.upper() == "VIDEO"]
    if "Hook Text" in df.columns:
        df = df[df["Hook Text"].astype(str).str.strip().ne("")]
    else:
        df = df.iloc[0:0]

    word_to_vals = {}

    for _, row in df.iterrows():
        tokens = _tokenize_hook_text(row.get("Hook Text", ""))
        if not tokens:
            continue

        engagement = _get_metric_value(row, metric)
        for tok in set(tokens):
            word_to_vals.setdefault(tok, []).append(float(engagement))

    rows = []
    for w, vals in word_to_vals.items():
        avg_engagement = sum(vals) / max(1, len(vals))
        rows.append((w, avg_engagement))

    stats = pd.DataFrame(rows, columns=["word", "engagement_weight"]).sort_values(
        "engagement_weight", ascending=False
    )

    hook_top_words = stats.head(5).copy()

    if stats.empty:
        hook_wordcloud_path = ""
        if state:
            state.hook_wordcloud_path = hook_wordcloud_path
            state.hook_top_words = hook_top_words
        return

    # WordCloud expects a "frequency" dict — we feed engagement-weight instead.
    engagement_weights = {
        r.word: math.log1p(max(0.0, float(r.engagement_weight)))
        for r in stats.itertuples()
    }

    mn = float(stats["engagement_weight"].min())
    mx = float(stats["engagement_weight"].max())
    denom = (mx - mn) if (mx - mn) != 0 else 1.0

    stats_index = stats.set_index("word")["engagement_weight"].to_dict()

    def color_func(word, *args, **kwargs):
        v = float(stats_index.get(word, mn))
        norm = (v - mn) / denom
        hue = (240.0 - 220.0 * norm) / 360.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 0.95)
        return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

    wc = WordCloud(
        width=1400,
        height=700,
        background_color="white",
        collocations=False,
        prefer_horizontal=0.95,
    ).generate_from_frequencies(engagement_weights)

    wc = wc.recolor(color_func=color_func)
    wc.to_file("hook_wordcloud.png")

    hook_wordcloud_path = "hook_wordcloud.png"

    if state:
        state.hook_wordcloud_path = hook_wordcloud_path
        state.hook_top_words = hook_top_words


def update_hook_wordcloud(state):
    generate_hook_wordcloud(state.hook_metric, state)


# -------------------------------
# Minimal UI (as in your last provided file)
# -------------------------------
semantics_layout = """
# 💬 Semantics: Hook Word Cloud (Engagement-Weighted)

Color & size words by:

<|{hook_metric}|selector|lov={hook_metric_lov}|dropdown|on_change=update_hook_wordcloud|>

<|layout|columns=1 1|
<|{hook_wordcloud_path}|image|width=100%|>
<||>
|>

---

## 🔎 Top words
<|{hook_top_words}|table|page_size=5|>
"""

engagement_dashboard_layout = """
# 📊 Account Engagement Overview

## 👁️ Profile Views (Yesterday)
<|{profile_views}|text|class_name=metric-number|>
"""

pages = {
    "Semantics_Sentiment": semantics_layout,
    "Engagement_Dashboard": engagement_dashboard_layout,
}


if __name__ == "__main__":
    app = Gui(pages=pages)

    app.run(
        title="Malugo Analytics ✨",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        dark_mode=True,
    )
