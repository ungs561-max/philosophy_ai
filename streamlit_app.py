
import streamlit as st

st.title("📚 철학자의 서재")

st.write("철학자와 함께 당신의 고민을 생각해 보세요.")

philosopher = st.selectbox(
    "대화할 철학자를 선택하세요",
    ["장자", "소크라테스", "에피쿠로스"]
)

worry = st.text_area("어떤 고민이 있나요?")

if st.button("상담 시작"):
    if worry.strip():
        st.success(f"{philosopher}에게 고민이 전달되었습니다!")
        st.write("입력한 고민:", worry)
    else:
        st.warning("고민을 먼저 입력해 주세요.")
  
