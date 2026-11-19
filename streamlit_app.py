import base64
import html
import random
import re
import uuid
from pathlib import Path

import requests
import streamlit as st


# Streamlit 명령보다 먼저 실행해야 합니다.
st.set_page_config(page_title="철학자의 서재", page_icon="📚")

BASE_DIR = Path(__file__).parent
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"
MODES = {
    "상담 모드": {
        "key_name": "DIFY_COUNSEL_KEY",
        "description": "고민을 나누고 철학적 조언을 받아보세요.",
        "placeholder": "요즘 어떤 고민이 있나요?",
    },
    "철학공부 모드": {
        "key_name": "DIFY_STUDY_KEY",
        "description": "철학자의 사상과 저서에 대해 질문해 보세요.",
        "placeholder": "어떤 철학 개념이 궁금한가요?",
    },
}


def set_library_background():
    image_path = BASE_DIR / "library_bg.png"
    if not image_path.exists():
        st.warning("배경 이미지 library_bg.png 파일을 찾을 수 없습니다.")
        return

    encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    st.html(
        f"""
<style>
.stApp {{
    background-image: linear-gradient(rgba(20,12,5,.55), rgba(20,12,5,.55)),
        url("data:image/png;base64,{encoded_image}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label {{
    color: #FFF4DE;
}}
</style>
"""
    )


@st.cache_data(show_spinner=False)
def load_quotes():
    file_path = BASE_DIR / "quotes.txt"
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"(?m)^\s*-\s*명언\s*:\s*", content)
    quotes = []

    for block in blocks[1:]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue

        quote = lines[0].strip(' "“”')
        question_line = next(
            (line for line in lines[1:] if re.match(r"^-?\s*성찰 질문\s*:", line)),
            None,
        )
        if question_line is None:
            continue

        question = re.sub(r"^-?\s*성찰 질문\s*:\s*", "", question_line)
        philosopher = lines[-1].strip()
        if quote and question and philosopher:
            quotes.append(
                {"quote": quote, "question": question, "philosopher": philosopher}
            )
    return quotes


def initialize_state():
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    if "conversations" not in st.session_state:
        st.session_state.conversations = {name: "" for name in MODES}
    if "histories" not in st.session_state:
        st.session_state.histories = {name: [] for name in MODES}
    if "active_mode" not in st.session_state:
        st.session_state.active_mode = "상담 모드"
    if "pending_reflection" not in st.session_state:
        st.session_state.pending_reflection = None
    if "selected_quote" not in st.session_state:
        quotes = load_quotes()
        st.session_state.selected_quote = random.choice(quotes) if quotes else None


def start_reflection():
    """모드 선택 radio보다 나중에 클릭돼도 callback에서 안전하게 전환."""
    selected = st.session_state.selected_quote
    if selected is None:
        return

    st.session_state.active_mode = "상담 모드"
    st.session_state.conversations["상담 모드"] = ""
    st.session_state.histories["상담 모드"] = []
    st.session_state.pending_reflection = selected.copy()


def reset_conversation():
    mode = st.session_state.active_mode
    st.session_state.conversations[mode] = ""
    st.session_state.histories[mode] = []
    st.session_state.pending_reflection = None


def show_quote_card():
    selected = st.session_state.selected_quote
    if selected is None:
        st.caption("quotes.txt 파일에 표시할 명언이 없습니다.")
        return

    quote = html.escape(selected["quote"])
    question = html.escape(selected["question"])
    philosopher = html.escape(selected["philosopher"])

    # Streamlit 기본 버튼도 카드 안에 포함하므로 버튼 클릭 시 Python이 실행됩니다.
    st.html(
        """
<style>
/* Desktop: 우측 배경 위에 고정 */
.st-key-quote_card {
    position: fixed;
    top: 43%;
    right: 5%;
    width: 320px;
    max-width: 25vw;
    z-index: 50;
    padding: 20px 22px 17px;
    background: rgba(42,29,20,.91);
    border: 1px solid rgba(210,170,105,.6);
    border-radius: 14px;
    box-shadow: 0 8px 25px rgba(0,0,0,.30);
    box-sizing: border-box;
}
.st-key-quote_card .quote-heading {
    font-size: 13px;
    color: #ddbd86;
    margin-bottom: 15px;
}
.st-key-quote_card .quote-main {
    font-size: 19px;
    font-weight: 650;
    line-height: 1.65;
    color: #fff2db;
    overflow-wrap: anywhere;
    margin-bottom: 16px;
}
.st-key-quote_card .quote-question {
    border-top: 1px solid #806548;
    padding-top: 13px;
    font-size: 13px;
    line-height: 1.7;
    color: #e5d2b5;
    overflow-wrap: anywhere;
}
.st-key-quote_card .quote-author {
    margin: 14px 0 12px;
    text-align: right;
    font-size: 12px;
    color: #d5ae78;
}
.st-key-quote_card .stButton > button {
    width: 100%;
    color: #2d2114;
    background: #d8b47b;
    border: 0;
    font-weight: 650;
}
.st-key-quote_card .stButton > button:hover {
    color: #2d2114;
    background: #eccb97;
}
/* 태블릿/모바일: 일반 콘텐츠 흐름으로 이동해 상담 화면을 가리지 않음 */
@media (max-width: 950px) {
    .st-key-quote_card {
        position: relative;
        top: auto;
        right: auto;
        width: 100%;
        max-width: 100%;
        margin: 18px 0 22px;
    }
    .st-key-quote_card .quote-main { font-size: 17px; }
    .stApp { background-attachment: scroll; }
}
</style>
"""
    )

    with st.container(key="quote_card"):
        st.html(
            f"""
<div class="quote-heading">✦ 서재의 한 문장</div>
<div class="quote-main">“{quote}”</div>
<div class="quote-question">{question}</div>
<div class="quote-author">— {philosopher}</div>
"""
        )
        st.button(
            "이 질문으로 대화하기",
            key="start_reflection_button",
            on_click=start_reflection,
            use_container_width=True,
        )


def send_to_dify(question, mode, api_key):
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
            "conversation_id": st.session_state.conversations[mode],
            "user": st.session_state.user_id,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def show_dify_error(error):
    if isinstance(error, requests.exceptions.HTTPError):
        response = error.response
        st.error(f"API 오류: {response.status_code}")
        try:
            data = response.json()
            st.write(f"오류 유형: {data.get('code', '알 수 없음')}")
            if "quota" in str(data.get("message", "")).lower():
                st.warning("AI 모델 사용량 한도를 확인해 주세요.")
        except ValueError:
            pass
    elif isinstance(error, requests.exceptions.RequestException):
        st.error("Dify 서버에 연결할 수 없습니다.")
    else:
        st.error("AI 응답을 읽을 수 없습니다.")


# ===== 실제 화면 구성 =====
set_library_background()
initialize_state()

st.title("📚 철학자의 서재")
st.write("철학자와 함께 고민을 나누거나 철학을 공부해 보세요.")

# 모바일에서는 제목 아래에 표시되고, PC에서는 CSS로 오른쪽에 고정됩니다.
show_quote_card()

mode = st.radio(
    "이용할 모드를 선택하세요",
    list(MODES.keys()),
    horizontal=True,
    key="active_mode",
)
config = MODES[mode]
st.info(config["description"])

if config["key_name"] not in st.secrets:
    st.error("해당 모드의 API 키가 등록되지 않았습니다.")
    st.stop()
api_key = st.secrets[config["key_name"]]

st.button("새 대화 시작", on_click=reset_conversation)

for message in st.session_state.histories[mode]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# 명언 버튼을 통해 시작한 경우 사용자가 읽을 수 있는 문구와 Dify 지시를 분리
reflection = st.session_state.pending_reflection if mode == "상담 모드" else None
question = st.chat_input(config["placeholder"])

if reflection is not None:
    st.session_state.pending_reflection = None
    visible_question = (
        f"{reflection['philosopher']}의 명언을 바탕으로 "
        f"'{reflection['question']}'에 관해 이야기해 보고 싶어요."
    )
    api_question = (
        "다음 명언과 성찰 질문으로 철학 상담을 시작해 주세요. "
        "성찰 질문에 대신 답하지 말고, 저의 경험을 자연스럽게 물어봐 주세요. "
        "응답은 짧고 공감적으로 해 주세요.\n\n"
        f"철학자: {reflection['philosopher']}\n"
        f"명언: {reflection['quote']}\n"
        f"성찰 질문: {reflection['question']}"
    )
elif question:
    visible_question = question
    api_question = question
else:
    visible_question = None
    api_question = None

if api_question:
    st.session_state.histories[mode].append(
        {"role": "user", "content": visible_question}
    )
    with st.chat_message("user"):
        st.write(visible_question)

    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하고 있습니다..."):
            try:
                result = send_to_dify(api_question, mode, api_key)
                answer = result.get("answer", "답변을 생성하지 못했습니다.")
                st.session_state.conversations[mode] = result.get(
                    "conversation_id", st.session_state.conversations[mode]
                )
                st.write(answer)
                st.session_state.histories[mode].append(
                    {"role": "assistant", "content": answer}
                )
            except (requests.exceptions.RequestException, ValueError) as error:
                show_dify_error(error)
