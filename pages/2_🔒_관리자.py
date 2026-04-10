"""통합 관리자 페이지 - Q&A 챗봇 + 포트폴리오 코치"""
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="관리자",
    page_icon="🔒",
    layout="wide",
)

st.title("🔒 관리자 대시보드")

# 비밀번호 게이트
ADMIN_PW = os.getenv("ADMIN_PASSWORD", "admin1234")

if "unified_admin_authed" not in st.session_state:
    st.session_state.unified_admin_authed = False

if not st.session_state.unified_admin_authed:
    pw = st.text_input("관리자 비밀번호", type="password", key="unified_admin_pw_input")
    if pw:
        if pw == ADMIN_PW:
            st.session_state.unified_admin_authed = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()

# 인증 후
tab_pf, tab_qa = st.tabs(["📋 포트폴리오 코치", "🎓 Q&A 챗봇"])

with tab_pf:
    from portfolio.admin import render as render_portfolio_admin
    render_portfolio_admin()

with tab_qa:
    # === 기존 app.py에서 옮겨온 Q&A 관리자 로직 ===
    from rag import db

    qa_tab1, qa_tab2, qa_tab3 = st.tabs(["📋 로그", "💬 피드백", "📊 통계"])

    with qa_tab1:
        logs = db.select("logs", {"order": "created_at.desc"}, limit=50)
        if logs:
            st.dataframe(
                [{"시간": l.get("created_at", "")[:19], "세션": l.get("session_id", ""),
                  "질문": l.get("question", ""), "캐시": l.get("cached", False)} for l in logs],
                use_container_width=True,
            )
        else:
            st.info("로그가 없습니다.")

    with qa_tab2:
        fb = db.select("feedback", {"order": "created_at.desc"}, limit=50)
        if fb:
            st.dataframe(
                [{"시간": f.get("created_at", "")[:19], "세션": f.get("session_id", ""),
                  "질문": f.get("question", ""), "피드백": f.get("feedback_type", "")} for f in fb],
                use_container_width=True,
            )
        else:
            st.info("피드백이 없습니다.")

    with qa_tab3:
        total_logs = len(db.select("logs", limit=1000))
        total_fb = len(db.select("feedback", limit=1000))
        unhelpful = len([f for f in db.select("feedback", {"feedback_type": "eq.unhelpful"}, limit=1000)])

        c1, c2, c3 = st.columns(3)
        c1.metric("총 질문 수", total_logs)
        c2.metric("피드백 수", total_fb)
        c3.metric("👎 비율", f"{(unhelpful/total_fb*100):.0f}%" if total_fb > 0 else "0%")
