

import streamlit as st
import base64
from pathlib import Path

# 도서관 배경 이미지 불러오기
def set_library_background():
    image_path = Path(__file__).parent / "library_bg.png"

    with open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(
            image_file.read()
        ).decode()

    st.html(f"""
    <style>
    .stApp {{
        background-image:
            linear-gradient(
                rgba(20, 12, 5, 0.55),
                rgba(20, 12, 5, 0.55)
            ),
            url("data:image/png;base64,{encoded_image}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}

    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp p,
    .stApp label {{
        color: #FFF4DE;
    }}
    </style>
    """)

# 배경 적용
set_library_background()
import requests
import uuid
st.set_page_config(
    page_title="철학자의 서재",
    page_icon="📚"
)

st.title("📚 철학자의 서재")
st.write("철학자와 함께 고민을 나누거나 철학을 공부해 보세요.")

# 1. 두 개의 Dify 앱 설정
MODES = {
    "상담 모드": {
        "key_name": "DIFY_COUNSEL_KEY",
        "description": "고민을 나누고 철학적 조언을 받아보세요.",
        "placeholder": "요즘 어떤 고민이 있나요?"
    },
    "철학공부 모드": {
        "key_name": "DIFY_STUDY_KEY",
        "description": "철학자의 사상과 저서에 대해 질문해 보세요.",
        "placeholder": "어떤 철학 개념이 궁금한가요?"
    }
}

DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"

# 2. 모드 선택
mode = st.radio(
    "이용할 모드를 선택하세요",
    list(MODES.keys()),
    horizontal=True
)

config = MODES[mode]
st.info(config["description"])

# 3. API 키 확인
if config["key_name"] not in st.secrets:
    st.error("해당 모드의 API 키가 등록되지 않았습니다.")
    st.stop()

api_key = st.secrets[config["key_name"]]

# 4. 사용자 및 모드별 대화 기록
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "conversations" not in st.session_state:
    st.session_state.conversations = {
        name: "" for name in MODES
    }

if "histories" not in st.session_state:
    st.session_state.histories = {
        name: [] for name in MODES
    }

# 5. 대화 초기화
if st.button("새 대화 시작"):
    st.session_state.conversations[mode] = ""
    st.session_state.histories[mode] = []
    st.rerun()

# 6. 이전 대화 표시
for message in st.session_state.histories[mode]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# 7. 질문 입력
question = st.chat_input(config["placeholder"])

if question:
    st.session_state.histories[mode].append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.write(question)

    # 8. 해당 모드의 Dify API 호출
    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하고 있습니다..."):
            try:
                response = requests.post(
                    DIFY_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "inputs": {},
                        "query": question,
                        "response_mode": "blocking",
                        "conversation_id": (
                            st.session_state.conversations[mode]
                        ),
                        "user": st.session_state.user_id
                    },
                    timeout=120
                )

                response.raise_for_status()
                result = response.json()

                answer = result.get(
                    "answer", "답변을 생성하지 못했습니다."
                )

                st.session_state.conversations[mode] = (
                    result.get("conversation_id", "")
                )

                st.write(answer)

                st.session_state.histories[mode].append({
                    "role": "assistant",
                    "content": answer
                })

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code

                try:
                    error_data = e.response.json()
                    error_code = error_data.get(
                        "code", "알 수 없음"
                    )
                    error_message = error_data.get(
                        "message", ""
                    )
                except ValueError:
                    error_code = "알 수 없음"
                    error_message = ""

                st.error(f"API 오류: {status}")
                st.write(f"오류 유형: {error_code}")

                if "quota" in str(error_message).lower():
                    st.warning(
                        "AI 모델 사용량 한도를 확인해 주세요."
                    )

            except requests.exceptions.RequestException:
                st.error("Dify 서버에 연결할 수 없습니다.")

            except ValueError:
                st.error("AI 응답을 읽을 수 없습니다.")
