
import streamlit as st
import requests
import uuid

st.title("📚 철학자의 서재")
st.write("철학자와 함께 당신의 고민을 생각해 보세요.")

philosopher = st.selectbox(
    "대화할 철학자를 선택하세요",
    ["장자", "소크라테스", "에피쿠로스"]
)

worry = st.text_area("어떤 고민이 있나요?")

# Dify API 설정
DIFY_API_KEY = st.secrets["DIFY_API_KEY"]
DIFY_API_URL = "https://api.dify.ai/v1/chat-messages"

# 사용자 식별값
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = ""

# 철학자 변경 시 새 대화 시작
if "selected_philosopher" not in st.session_state:
    st.session_state.selected_philosopher = philosopher

if st.session_state.selected_philosopher != philosopher:
    st.session_state.conversation_id = ""
    st.session_state.selected_philosopher = philosopher

if st.button("상담 시작"):
    if not worry.strip():
        st.warning("고민을 먼저 입력해 주세요.")
    else:
        with st.spinner("철학자가 답변을 준비하고 있습니다..."):
            try:
                response = requests.post(
                    DIFY_API_URL,
                    headers={
                        "Authorization": f"Bearer {DIFY_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "inputs": {},
                        "query": (
                            f"{philosopher}의 관점에서 "
                            f"다음 고민을 상담해 주세요: {worry}"
                        ),
                        "response_mode": "blocking",
                        "conversation_id": st.session_state.conversation_id,
                        "user": st.session_state.user_id
                    },
                    timeout=120
                )

                response.raise_for_status()
                result = response.json()

                st.session_state.conversation_id = result.get(
                    "conversation_id", ""
                )

                st.subheader(f"💬 {philosopher}의 답변")
                st.write(result.get("answer", "답변이 없습니다."))

            except requests.exceptions.RequestException:
                st.error("Dify API 연결에 실패했습니다.")
            except ValueError:
                st.error("API 응답을 읽을 수 없습니다.")
