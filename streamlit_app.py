import logging
import os
from hashlib import sha256
from threading import Lock, Thread

import streamlit as st
from streamlit import runtime

from dialogue import (
    MODES, PROFILES, QUOTES, ROOT, SECRET_NAMES, UUID, DialogueError,
    daily_cards, picture_paths, run_dialogue,
)

st.set_page_config(page_title="철학자의 서재", page_icon="📚", layout="wide")
st.html("""<style>
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] { display:none; }
[data-testid="stMainBlockContainer"] { padding:0; max-width:none; }
@media (max-width: 800px) {
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow: hidden; }
}
</style>""")

FRONTEND = ROOT / "frontend"
COMPONENT_KEY = "philosopher_library"
STUDY_ENABLED = frozenset({"epictetus"})
DEMO_ENABLED = os.environ.get("PHILOSOPHY_DEMO") == "1"


def secret(name):
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None
    value = value or os.environ.get(name)
    return value.strip() if isinstance(value, str) and value.strip() else None


class DialogueJob:
    def __init__(self, request_id):
        self._lock = Lock()
        self._state = {"requestId": request_id, "done": False}

    def publish(self, **update):
        with self._lock:
            self._state.update(update)

    def snapshot(self):
        with self._lock:
            return self._state.copy()


def valid_payload(value):
    if not isinstance(value, dict):
        return False
    slug, mode = value.get("id"), value.get("mode")
    if not isinstance(slug, str) or slug not in PROFILES or mode not in MODES:
        return False
    if mode == "study" and slug not in STUDY_ENABLED:
        return False
    for name in ("requestId", "user", "conversationId"):
        token = value.get(name)
        if not isinstance(token, str) or (not UUID.fullmatch(token) and (name != "conversationId" or token)):
            return False
    text = value.get("text")
    return (
        isinstance(value.get("test"), bool) and (DEMO_ENABLED or not value["test"])
        and isinstance(value.get("fromCard"), bool)
        and isinstance(text, str) and len(text) <= 4000 and (value["fromCard"] or bool(text.strip()))
    )


def start_request():
    value = st.session_state[COMPONENT_KEY].request
    if not valid_payload(value):
        return
    previous = st.session_state.get("dialogue_job")
    if previous:
        current = previous.snapshot()
        if not current["done"] or current["requestId"] == value["requestId"]:
            return
    job = DialogueJob(value["requestId"])
    st.session_state.dialogue_job = job
    key = None if value["test"] else secret(SECRET_NAMES[value["id"]][MODES.index(value["mode"])])
    slug, mode = value["id"], value["mode"]
    quote_id = value.get("quoteId")
    if mode == "study":
        card = daily_cards()[slug][mode]
    else:
        card = QUOTES[slug].get(quote_id) if isinstance(quote_id, str) else None

    def work():
        try:
            if value["fromCard"] and card is None:
                raise DialogueError("오늘의 카드를 불러올 수 없습니다.")
            run_dialogue(value, key, card, job.publish)
        except DialogueError as error:
            job.publish(error=str(error), done=True)
        except Exception as error:
            logging.getLogger(__name__).warning("Dialogue job failed (%s)", type(error).__name__)
            job.publish(error="대화 요청을 처리하지 못했습니다.", done=True)

    Thread(target=work, daemon=True).start()


@st.cache_resource
def component_renderer(html, css, js):
    revision = sha256("\0".join((html, css, js)).encode()).hexdigest()[:16]
    return st.components.v2.component(
        f"{COMPONENT_KEY}_{revision}", html=html, css=css, js=js,
    )


cards = daily_cards()
media = runtime.get_instance().media_file_mgr
font_directory = ROOT / "static" / "fonts"
pretendard_url = media.add(str(font_directory / "PretendardVariable.woff2"), "font/woff2", "library-font-pretendard")
ridi_url = media.add(str(font_directory / "RIDIBatang.otf"), "font/otf", "library-font-ridibatang")
# Register the faces in the document so the shadow-root component can use them.
st.html(f"""<style>
@font-face {{
    font-family: "Pretendard";
    src: url(".{pretendard_url}") format("woff2");
    font-style: normal;
    font-weight: 100 900;
    font-display: swap;
}}
@font-face {{
    font-family: "RIDIBatang";
    src: url(".{ridi_url}") format("opentype");
    font-style: normal;
    font-weight: 400;
    font-display: swap;
}}
</style>""")
avatar_names = {
    "epictetus": "epictetus",
    "laozi": "laozi",
    "smith": "adam_smith",
    "camus": "albert_camus",
}
public_profiles = {
    slug: {**{name: profile[name] for name in ("name", "latin", "school", "place", "era", "intro", "greeting", "detailed_description", "waiting_messages")},
           # Use Streamlit's media route with the browser's current app prefix,
           # including the prefix when Community Cloud embeds the app.
           "avatar": "." + media.add(
               str(ROOT / "static" / "profiles" / f"{avatar_names[slug]}.png"),
               "image/png", f"philosopher-{slug}-avatar",
           ),
           "art": {
               pose: "." + media.add(str(path), "image/png", f"philosopher-{slug}-{pose}")
               for pose, path in picture_paths(profile).items()
           }}
    for slug, profile in PROFILES.items()
}
config = {
    "demo": DEMO_ENABLED,
    "studyEnabled": sorted(STUDY_ENABLED),
    "profiles": {
        slug: {mode: {"available": bool(secret(name)), "card": cards[slug].get(mode)}
               for mode, name in zip(MODES, names, strict=True)}
        for slug, names in SECRET_NAMES.items()
    },
    "quotes": {slug: list(pool.values()) for slug, pool in QUOTES.items()},
}
renderer = component_renderer(*(
    (FRONTEND / name).read_text(encoding="utf-8-sig")
    for name in ("index.html", "styles.css", "app.mjs")
))


@st.fragment
def render_library():
    # Polling reruns only this fragment so it does not reread the PNGs.
    job = st.session_state.get("dialogue_job")
    renderer(
        key=COMPONENT_KEY,
        data={"profiles": public_profiles, "config": config, "snapshot": job.snapshot() if job else None},
        on_request_change=start_request,
        on_poll_change=lambda: None,
    )


render_library()
