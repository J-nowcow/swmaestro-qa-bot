"""SW마에스트로 Q&A 챗봇 - Streamlit 앱"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from rag.chain import ask, semantic_search
from rag.feedback import log_feedback
from rag.cache import load_popular_cache

# 페이지 설정
st.set_page_config(
    page_title="SW마에스트로 Q&A",
    page_icon="🎓",
    layout="centered",
)

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
    st.markdown("**문의**")
    st.markdown("02-6933-0701~5")
    st.markdown("swmaestro@fkii.org")
    st.caption("서울특별시 마포구 마포대로 89\n포스트타워 7층, 12층")
    st.divider()
    st.caption("이 챗봇은 공식 사이트 정보 기반이며,\n최신 정보와 다를 수 있습니다.")
    import hashlib, time as _time
    cache_bust = hashlib.md5(str(int(_time.time() // 300)).encode()).hexdigest()[:6]
    st.markdown(f"[![GitHub stars](https://img.shields.io/github/stars/J-nowcow/swmaestro-qa-bot?style=social&v={cache_bust})](https://github.com/J-nowcow/swmaestro-qa-bot)")
    st.caption("GitHub Star는 사랑입니다 :)")

    if st.button("대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_question = None
        st.rerun()

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "popular_items" not in st.session_state:
    st.session_state.popular_items = load_popular_cache()

# 헤더
st.markdown("# 🎓 SW마에스트로 Q&A")

# ─── 탭 구성 ───
tab_chat, tab_search, tab_popular = st.tabs(["💬 채팅", "📚 검색", "⭐ 인기 질문"])

# ═══════════════════════════════════════
# 💬 채팅 탭
# ═══════════════════════════════════════
with tab_chat:
    st.markdown("AI·SW마에스트로에 대해 궁금한 점을 물어보세요!")

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
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # 어시스턴트 답변에 피드백 버튼
            if msg["role"] == "assistant" and not msg.get("feedback_given"):
                c1, c2, c3 = st.columns([1, 1, 4])
                with c1:
                    if st.button("👍", key=f"up_{idx}"):
                        log_feedback(
                            st.session_state.messages[idx - 1]["content"],
                            msg["content"], "helpful", st.session_state.session_id
                        )
                        msg["feedback_given"] = True
                        st.rerun()
                with c2:
                    if st.button("👎", key=f"down_{idx}"):
                        log_feedback(
                            st.session_state.messages[idx - 1]["content"],
                            msg["content"], "unhelpful", st.session_state.session_id
                        )
                        msg["feedback_given"] = True
                        st.rerun()
                with c3:
                    if st.button("✏️ 의견 남기기", key=f"comment_{idx}"):
                        msg["show_comment"] = True
                        st.rerun()
            if msg["role"] == "assistant" and msg.get("show_comment") and not msg.get("comment_sent"):
                comment = st.text_input("의견을 남겨주세요", key=f"comment_text_{idx}")
                if comment and st.button("전송", key=f"comment_send_{idx}"):
                    log_feedback(
                        st.session_state.messages[idx - 1]["content"],
                        msg["content"], f"comment: {comment}", st.session_state.session_id
                    )
                    msg["comment_sent"] = True
                    st.success("의견 감사합니다!")
                    st.rerun()

    # 새 질문 처리
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
            status_placeholder = st.empty()
            with st.spinner("답변을 찾고 있어요..."):
                history = st.session_state.messages[:-1] if len(st.session_state.messages) > 1 else None

                def on_fallback(msg):
                    status_placeholder.warning(msg)

                answer, used_fallback = ask(new_question, chat_history=history, status_callback=on_fallback, session_id=st.session_state.session_id)

            status_placeholder.empty()
            if used_fallback:
                st.info("요청이 많아 대체 모델로 답변했습니다. 답변 품질이 다소 떨어질 수 있습니다.")
            st.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.rerun()

# ═══════════════════════════════════════
# 📚 검색 탭
# ═══════════════════════════════════════
with tab_search:
    st.markdown("의미 기반으로 관련 정보를 검색합니다. (LLM 미사용, 빠름)")

    query = st.text_input("검색어를 입력하세요", placeholder="예: 코딩테스트 준비 방법", key="search_input")

    if query:
        with st.spinner("검색 중..."):
            results = semantic_search(query, top_k=5)

        if results:
            for i, r in enumerate(results, 1):
                sim_pct = r["similarity"] * 100
                with st.container(border=True):
                    st.markdown(f"**{i}. {r['page_title']} — {r['section']}**")
                    st.caption(f"유사도: {sim_pct:.1f}%")
                    st.markdown(r["content"][:300] + ("..." if len(r["content"]) > 300 else ""))
                    st.markdown(f"[원문 보기]({r['source_url']})")
        else:
            st.warning("검색 결과가 없습니다.")

# ═══════════════════════════════════════
# ⭐ 인기 질문 탭
# ═══════════════════════════════════════
with tab_popular:
    st.markdown("자주 묻는 질문들을 모아놓았습니다.")

    if st.session_state.popular_items:
        for item in st.session_state.popular_items:
            with st.expander(item["question"]):
                st.markdown(item["answer"])
    else:
        st.info("인기 질문 데이터가 아직 준비되지 않았습니다.")

