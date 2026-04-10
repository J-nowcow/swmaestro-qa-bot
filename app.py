"""SW마에스트로 멘티 도구 - 메인 entry (navigation hub)"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="SW마에스트로 멘티 도구",
    page_icon="📋",
    layout="centered",
)

# 페이지 정의 (사이드바 표시 순서)
portfolio_page = st.Page(
    "page_views/portfolio_coach.py",
    title="포트폴리오 코치",
    icon="📋",
    default=True,
)
qa_page = st.Page(
    "page_views/qa_chatbot.py",
    title="Q&A 챗봇",
    icon="🎓",
)
admin_page = st.Page(
    "page_views/admin.py",
    title="관리자",
    icon="🔒",
)

nav = st.navigation([portfolio_page, qa_page, admin_page])
nav.run()
