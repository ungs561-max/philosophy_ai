import base64
import hashlib
import html
import random
import re
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import streamlit as st

# Streamlit 페이지 설정은 다른 Streamlit 출력보다 먼저 실행합니다.
st.set_page_config(page_title="철학자의 서재", page_icon="📚")

BASE_DIR = Path(__file__).parent
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"

MODES = {
    "상담 모드": {
        "description": "고민을 나누고 철학적 조언을 받아보세요.",
        "placeholder": "요즘 어떤 고민이 있나요?",
    },
    "철학공부 모드": {
        "description": "철학자의 사상과 저서에 대해 질문해 보세요.",
        "placeholder": "어떤 철학 개념이 궁금한가요?",
    },
}

# 철학자별 Dify Secrets 이름. 연결 전 항목은 None으로 설정합니다.
PHILOSOPHERS = {
    "에픽테토스": {
        "상담 모드": "DIFY_COUNSEL_KEY",
        "철학공부 모드": "DIFY_STUDY_KEY",
    },
    "애덤 스미스": {
        "상담 모드": "DIFY_SMITH_COUNSEL_KEY",
        "철학공부 모드": "DIFY_SMITH_STUDY_KEY",
    },
    "coming_1": None,
    "coming_2": None,
}

# 개념을 늘리고 싶다면 이 목록에 같은 형식으로 추가하면 됩니다.
# 'explanation'은 원전의 직인용이 아닌 학습용 핵심 요약입니다.
PHILOSOPHY_CONCEPTS = [
    {
        "term": "인(仁)",
        "explanation": "인은 사람을 사랑하는 것이다.",
        "philosopher": "공자",
        "topic": "공자의 인(仁)",
    },
    {
        "term": "아파테이아(Apatheia)",
        "explanation": "통제할 수 없는 것에 대한 동요에서 벗어나 이성적으로 판단하는 태도.",
        "philosopher": "스토아 철학",
        "topic": "스토아 철학의 아파테이아",
    },
    {
        "term": "덕(아레테)",
        "explanation": "좋은 삶은 인간의 탁월한 성품과 올바른 실천에 관계된다.",
        "philosopher": "아리스토텔레스",
        "topic": "아리스토텔레스의 덕(아레테)",
    },
    {
        "term": "무위(無爲)",
        "explanation": "인위적인 강제를 줄이고 자연스러운 이치에 따르는 태도.",
        "philosopher": "노자",
        "topic": "노자의 무위(無爲)",
    },
    {
        "term": "공감(sympathy)",
        "explanation": "타인의 처지를 상상하며 그 감정과 행동을 평가하는 능력.",
        "philosopher": "애덤 스미스",
        "topic": "애덤 스미스의 도덕감정론에서 공감(sympathy)",
    },
]


def set_library_background():
    path = BASE_DIR / "library_bg.png"
    if not path.exists():
        st.warning("배경 이미지 library_bg.png를 찾을 수 없습니다.")
        return
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    st.html(f"""
<style>
.stApp {{
    background-image: linear-gradient(rgba(20,12,5,.55), rgba(20,12,5,.55)),
        url("data:image/png;base64,{encoded}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label {{ color: #FFF4DE; }}
.stApp .st-key-new_conversation_button button {{
    background: #D8B47B; color: #302013; border: 1px solid #B48A53;
    font-weight: 650;
}}
.stApp .st-key-new_conversation_button button:hover {{
    background: #EBCB96; color: #302013;
}}
@media(max-width:950px) {{ .stApp {{ background-attachment: scroll; }} }}
</style>
""")


@st.cache_data(show_spinner=False)
def load_quotes():
    path = BASE_DIR / "quotes.txt"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"(?m)^\s*-\s*명언\s*:\s*", text)
    result = []
    for block in blocks[1:]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        quote = lines[0].strip(' "“”')
        question = next((v for v in lines[1:] if re.match(r"^-?\s*성찰 질문\s*:", v)), None)
        if not question:
            continue
        question = re.sub(r"^-?\s*성찰 질문\s*:\s*", "", question)
        author = lines[-1]
        if quote and question and author:
            result.append({"quote": quote, "question": question, "philosopher": author})
    return result


def todays_concept():
    # 날짜가 바뀌면 전 사용자에게 다음 개념이 보입니다(한국 시간 기준).
    day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    index = int(hashlib.sha256(day.encode("utf-8")).hexdigest(), 16) % len(PHILOSOPHY_CONCEPTS)
    return PHILOSOPHY_CONCEPTS[index]


def initialize_state():
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    if "active_mode" not in st.session_state:
        st.session_state.active_mode = "상담 모드"
    if "active_philosopher" not in st.session_state:
        st.session_state.active_philosopher = "에픽테토스"
    if "conversations" not in st.session_state:
        st.session_state.conversations = {}
    if "histories" not in st.session_state:
        st.session_state.histories = {}
    if "pending_card" not in st.session_state:
        st.session_state.pending_card = None
    if "selected_quote" not in st.session_state:
        quotes = load_quotes()
        st.session_state.selected_quote = random.choice(quotes) if quotes else None


def conversation_key(mode=None, philosopher=None):
    return (
        philosopher if philosopher is not None else st.session_state.active_philosopher,
        mode if mode is not None else st.session_state.active_mode,
    )


def ensure_history(key):
    if key not in st.session_state.conversations:
        st.session_state.conversations[key] = ""
    if key not in st.session_state.histories:
        st.session_state.histories[key] = []


def start_from_card(target_mode, card):
    # 버튼 콜백은 radio 위젯이 생성되기 전에 상태를 변경할 수 있습니다.
    st.session_state.active_mode = target_mode
    key = conversation_key(mode=target_mode)
    ensure_history(key)
    st.session_state.conversations[key] = ""
    st.session_state.histories[key] = []
    st.session_state.pending_card = {"mode": target_mode, "data": card.copy()}


def reset_conversation():
    key = conversation_key()
    ensure_history(key)
    st.session_state.conversations[key] = ""
    st.session_state.histories[key] = []
    st.session_state.pending_card = None


def display_card():
    mode = st.session_state.active_mode
    card = st.session_state.selected_quote if mode == "상담 모드" else todays_concept()
    if card is None:
        st.caption("quotes.txt에서 명언을 불러오지 못했습니다.")
        return

    st.html("""
<style>
.st-key-feature_card {
    position: fixed;
    top: 43%; right: 5%; width: 320px; max-width: 25vw;
    padding: 20px 22px 17px; z-index: 50; box-sizing: border-box;
    background: rgba(42,29,20,.92);
    border: 1px solid rgba(210,170,105,.65);
    border-radius: 14px;
    box-shadow: 0 8px 25px rgba(0,0,0,.30);
}
.st-key-feature_card .card-heading {font-size:13px; color:#ddbd86; margin-bottom:16px;}
.st-key-feature_card .card-main {
    font-size:19px; font-weight:650; line-height:1.65;
    color:#fff2db; overflow-wrap:anywhere; margin-bottom:17px;
}
.st-key-feature_card .card-detail {
    border-top:1px solid #806548; padding-top:13px;
    font-size:13px; line-height:1.7; color:#e5d2b5;
    overflow-wrap:anywhere;
}
.st-key-feature_card .card-author {
    text-align:right; font-size:12px; color:#d5ae78; margin:14px 0 12px;
}
.st-key-feature_card .stButton > button {
    width:100%; color:#2d2114; background:#d8b47b; border:0; font-weight:650;
}
.st-key-feature_card .stButton > button:hover {
    color:#2d2114; background:#eccb97;
}
@media(max-width:950px) {
    .st-key-feature_card {
        position:relative; top:auto; right:auto;
        width:100%; max-width:100%; margin:18px 0 22px;
    }
    .st-key-feature_card .card-main {font-size:17px;}
}
</style>
""")

    with st.container(key="feature_card"):
        if mode == "상담 모드":
            quote = html.escape(card["quote"])
            question = html.escape(card["question"])
            author = html.escape(card["philosopher"])
            st.html(f"""
<div class="card-heading">✦ 오늘의 명언</div>
<div class="card-main">“{quote}”</div>
<div class="card-detail">{question}</div>
<div class="card-author">— {author}</div>
""")
            st.button(
                "이 질문으로 상담하기",
                key="start_quote_conversation",
                on_click=start_from_card,
                args=("상담 모드", card),
                use_container_width=True,
            )
        else:
            term = html.escape(card["term"])
            explanation = html.escape(card["explanation"])
            author = html.escape(card["philosopher"])
            st.html(f"""
<div class="card-heading">✦ 오늘의 철학 이론</div>
<div class="card-main">{term}</div>
<div class="card-detail">“{explanation}”</div>
<div class="card-author">— {author} · 개념 요약</div>
""")
            st.button(
                "이 개념을 공부하기",
                key="start_concept_study",
                on_click=start_from_card,
                args=("철학공부 모드", card),
                use_container_width=True,
            )


def display_intro(mode):
    if mode == "상담 모드":
        heading = "철학자의 서재에 오신 것을 환영합니다"
        content = """
<div class="intro-line">이곳은 철학자의 서재입니다.</div>
<div class="intro-line">철학자들은 고립에 처해 힘들어하고 있는 당신과 대화할 준비가 되어 있습니다.</div>
<div class="intro-line">지금 고민이 많으신가요?</div>
<div class="intro-highlight">그렇다면 지혜의 역사에 한 획을 그은 철학자들과 대화하며 삶의 의미에 대해 고민해 보시기 바랍니다.</div>
"""
    else:
        heading = "철학의 세계에 오신 것을 환영합니다"
        content = """
<div class="intro-line">철학자들이 남긴 사상과 지혜를 탐구하는 공간입니다.</div>
<div class="intro-line">궁금했던 철학 개념이나 철학자의 사상을 자유롭게 질문해 보세요.</div>
<div class="intro-highlight">오래된 질문 속에서 새로운 생각을 발견해 보세요.</div>
"""
    st.html(f"""
<style>
.library-intro {{
    max-width:704px; width:100%; padding:26px 30px; box-sizing:border-box;
    background:rgba(43,27,17,.94); border:2px solid #a77a48;
    border-left:9px solid #76502b; border-radius:10px;
    box-shadow:inset 0 0 0 3px rgba(196,151,91,.12), 0 8px 22px rgba(0,0,0,.3);
    margin:15px 0 22px;
}}
.library-intro .intro-label {{color:#d6aa6e; font-size:11px; letter-spacing:2px; margin-bottom:10px;}}
.library-intro .intro-title {{color:#fff1d9; font-size:21px; font-weight:700; line-height:1.5; margin-bottom:15px;}}
.library-intro .intro-divider {{height:1px; background:#8c653e; margin-bottom:17px;}}
.library-intro .intro-line {{color:#f1e1c8; font-size:15px; line-height:1.9; margin-bottom:12px; word-break:keep-all;}}
.library-intro .intro-highlight {{color:#eac48b; font-size:15px; font-weight:600; line-height:1.9; margin-top:14px; word-break:keep-all;}}
.library-intro .intro-footer {{color:#d6aa6e; text-align:right; font-size:12px; margin-top:20px;}}
@media(max-width:768px) {{
    .library-intro {{padding:19px 17px; margin-top:12px;}}
    .library-intro .intro-title {{font-size:18px;}}
    .library-intro .intro-line,.library-intro .intro-highlight {{font-size:14px;line-height:1.8;}}
}}
</style>
<div class="library-intro">
  <div class="intro-label">WELCOME TO THE LIBRARY</div>
  <div class="intro-title">📖 {html.escape(heading)}</div>
  <div class="intro-divider"></div>
  {content}
  <div class="intro-footer">— 철학자의 서재</div>
</div>
""")


def resolve_key(philosopher, mode):
    config = PHILOSOPHERS.get(philosopher)
    return config.get(mode) if config else None


def make_card_prompt(card_state):
    target_mode = card_state["mode"]
    card = card_state["data"]
    if target_mode == "상담 모드":
        public_text = (
            f"{card['philosopher']}의 명언을 바탕으로 '{card['question']}'에 대해 상담하고 싶어요."
        )
        api_text = (
            "다음 명언을 시작점으로 철학 상담을 해 주세요. "
            "성찰 질문에 AI가 대신 답하지 말고, 사용자의 경험을 묻는 짧고 자연스러운 질문으로 대화를 시작해 주세요.\n\n"
            f"철학자: {card['philosopher']}\n"
            f"명언: {card['quote']}\n"
            f"성찰 질문: {card['question']}"
        )
    else:
        public_text = f"오늘의 철학 개념 '{card['term']}'을 공부하고 싶어요."
        api_text = (
            f"'{card['topic']}' 개념을 처음 공부하는 대학생에게 알기 쉽게 설명해 주세요. "
            "먼저 개념을 간단히 정의하고, 관련 철학적 배경과 현실적인 예시를 설명한 뒤 "
            "이해도를 확인할 질문을 하나 제시해 주세요. "
            "다음 카드 문장은 원전 직인용이 아닐 수 있는 학습용 요약이므로 정확한 원문인 것처럼 소개하지 마세요.\n\n"
            f"오늘의 개념: {card['term']}\n"
            f"관련 철학자: {card['philosopher']}\n"
            f"핵심 요약: {card['explanation']}"
        )
    return public_text, api_text


def send_to_dify(question, key, api_key):
    response = requests.post(
        DIFY_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "inputs": {},
            "query": question,
            "response_mode": "blocking",
            "conversation_id": st.session_state.conversations[key],
            "user": st.session_state.user_id,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def render_typing_indicator():
    """답변 대기 중, 채팅 말풍선 안에서 움직이는 점 3개를 표시합니다."""
    return """
<style>
.philosophy-typing-wrap {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    margin: 6px 0;
}
.philosophy-typing-bubble {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 12px 15px;
    border-radius: 17px 17px 17px 5px;
    background: #758a9a;
    box-shadow: 0 2px 7px rgba(0, 0, 0, .20);
}
.philosophy-typing-dot {
    width: 9px;
    height: 9px;
    flex: 0 0 9px;
    border-radius: 50%;
    background: #ffe24a;
    animation: philosophy-typing-pulse 1.2s infinite ease-in-out;
}
.philosophy-typing-dot:nth-child(2) { animation-delay: .15s; }
.philosophy-typing-dot:nth-child(3) { animation-delay: .30s; }
@keyframes philosophy-typing-pulse {
    0%, 60%, 100% { transform: translateY(0); opacity: .45; }
    30% { transform: translateY(-4px); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
    .philosophy-typing-dot { animation: none; opacity: 1; }
}
</style>
<div class="philosophy-typing-wrap" role="status" aria-label="답변 작성 중">
    <div class="philosophy-typing-bubble" aria-hidden="true">
        <span class="philosophy-typing-dot"></span>
        <span class="philosophy-typing-dot"></span>
        <span class="philosophy-typing-dot"></span>
    </div>
</div>
"""


# ================== 화면 시작 ==================
set_library_background()
initialize_state()

st.title("📚 철학자의 서재")
st.write("철학자와 함께 고민을 나누거나 철학을 공부해 보세요.")

# 모드 선택 결과에 맞춰 우측 카드도 바뀝니다.
mode = st.radio(
    "이용할 모드를 선택하세요",
    list(MODES),
    horizontal=True,
    key="active_mode",
)

philosopher = st.selectbox(
    "대화할 철학자를 선택하세요",
    list(PHILOSOPHERS),
    key="active_philosopher",
    format_func=lambda name: "아직 오는 중..." if name.startswith("coming_") else name,
)

display_card()
display_intro(mode)

secret_name = resolve_key(philosopher, mode)
if secret_name is None:
    st.info("아직 오는 중... 새로운 철학자가 서재에 합류할 예정입니다.")
    st.stop()
if secret_name not in st.secrets:
    st.info(f"{philosopher}의 {mode} 연결을 준비 중입니다.")
    st.stop()

api_key = st.secrets[secret_name]
key = conversation_key()
ensure_history(key)

st.button("새 대화 시작", key="new_conversation_button", on_click=reset_conversation)

for message in st.session_state.histories[key]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input(MODES[mode]["placeholder"])
card_state = st.session_state.pending_card
if card_state is not None and card_state["mode"] == mode:
    st.session_state.pending_card = None
    public_question, api_question = make_card_prompt(card_state)
elif question:
    public_question, api_question = question, question
else:
    public_question, api_question = None, None

if api_question:
    st.session_state.histories[key].append({"role": "user", "content": public_question})
    with st.chat_message("user"):
        st.write(public_question)
    with st.chat_message("assistant"):
        # Streamlit의 기본 spinner 대신 CSS 말풍선 애니메이션 표시
        typing_placeholder = st.empty()
        typing_placeholder.html(render_typing_indicator())
        try:
            result = send_to_dify(api_question, key, api_key)
            answer = result.get("answer", "답변을 생성하지 못했습니다.")
            st.session_state.conversations[key] = result.get(
                "conversation_id", st.session_state.conversations[key]
            )
            typing_placeholder.empty()
            st.write(answer)
            st.session_state.histories[key].append(
                {"role": "assistant", "content": answer}
            )
        except requests.exceptions.HTTPError as error:
            typing_placeholder.empty()
            response = error.response
            st.error(f"API 오류: {response.status_code}")
            try:
                data = response.json()
                st.write(f"오류 유형: {data.get('code', '알 수 없음')}")
                if "quota" in str(data.get("message", "")).lower():
                    st.warning("AI 모델 사용량 한도를 확인해 주세요.")
            except ValueError:
                pass
        except requests.exceptions.RequestException:
            typing_placeholder.empty()
            st.error("Dify 서버에 연결할 수 없습니다.")
        except ValueError:
            typing_placeholder.empty()
            st.error("AI 응답을 읽을 수 없습니다.")
