"""SW마에스트로 포트폴리오 코치 (Streamlit multipage entry)."""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from portfolio.ui import render

st.set_page_config(
    page_title="포트폴리오 코치",
    page_icon="📋",
    layout="centered",
)

render()
