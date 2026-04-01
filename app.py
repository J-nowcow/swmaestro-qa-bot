"""SW마에스트로 Q&A 챗봇 - Streamlit 앱"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from rag.chain import ask

# 페이지 설정
st.set_page_config(
    page_title="SW마에스트로 Q&A",
    page_icon="🎓",
    layout="centered",
)

# 커스텀 CSS (모바일 최적화)
st.markdown("""
<style>
    .stChatMessage { max-width: 100%; }
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 800px; }
    h1 { font-size: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.markdown("## 🎓 AI·SW마에스트로")
    st.markdown(
        "공식 사이트의 공개 정보를 기반으로\n"
        "자주 묻는 질문에 답변합니다."
    )
    st.divider()
    st.markdown("**유용한 링크**")
    st.markdown("- [공식 사이트](https://swmaestro.ai)")
    st.markdown("- [연수생 FAQ](https://swmaestro.ai/sw/bbs/B0000004/list.do?menuNo=200021)")
    st.markdown("- [코딩테스트 FAQ](https://swmaestro.ai/sw/bbs/B0000021/list.do?menuNo=200090)")
    st.divider()
    st.caption("이 챗봇은 공식 사이트 정보 기반이며,\n최신 정보와 다를 수 있습니다.")

    if st.button("대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_question = None
        st.rerun()

# 헤더
st.markdown("# 🎓 SW마에스트로 Q&A")
st.markdown("AI·SW마에스트로에 대해 궁금한 점을 물어보세요!")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# 예시 질문 (첫 대화 시)
if not st.session_state.messages and st.session_state.pending_question is None:
    st.markdown("##### 💡 이런 것들을 물어볼 수 있어요")
    examples = [
        "SW마에스트로 지원 자격이 어떻게 되나요?",
        "코딩테스트는 어떻게 준비하면 되나요?",
        "연수생에게 제공되는 혜택은?",
        "멘토는 어떤 분들인가요?",
    ]
    cols = st.columns(2)
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(example, key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_question = example
                st.rerun()

# 대화 기록 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 새 질문 처리 (예시 버튼 또는 채팅 입력)
new_question = None

if st.session_state.pending_question:
    new_question = st.session_state.pending_question
    st.session_state.pending_question = None
elif prompt := st.chat_input("질문을 입력하세요..."):
    new_question = prompt

if new_question:
    st.session_state.messages.append({"role": "user", "content": new_question})
    with st.chat_message("user"):
        st.markdown(new_question)

    with st.chat_message("assistant"):
        with st.spinner("답변을 찾고 있어요..."):
            history = st.session_state.messages[:-1] if len(st.session_state.messages) > 1 else None
            answer = ask(new_question, chat_history=history)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
