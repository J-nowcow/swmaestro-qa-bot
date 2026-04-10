"""Admin section body for portfolio coach (used by pages/3_🔒_관리자.py).

No password gate, no expander — caller is responsible for those.
"""
from __future__ import annotations

import streamlit as st

from portfolio import storage


def render() -> None:
    st.markdown("### 제출 내역 (최근 50건)")
    rows = storage.list_submissions(limit=50)
    if not rows:
        st.info("아직 제출 내역이 없습니다.")
    else:
        display = []
        for r in rows:
            display.append(
                {
                    "시간": (r.get("created_at") or "")[:19],
                    "페이지": r.get("page_count"),
                    "이미지": r.get("image_count"),
                    "잘림": r.get("image_truncated"),
                    "모델": r.get("model_used"),
                    "BYOK": r.get("used_byok"),
                    "폴백": r.get("used_fallback"),
                    "상태": r.get("status"),
                    "총평": (r.get("eval_summary") or "")[:60],
                    "경로": r.get("storage_path"),
                }
            )
        st.dataframe(display, use_container_width=True)

        st.markdown("### 다운로드 (storage path 입력)")
        target = st.text_input(
            "Storage path 복사 입력",
            key="portfolio_admin_dl_target",
            placeholder="20260409/154200-abc123",
        )
        if target:
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📦 zip 다운로드 URL 생성", key="dl_zip_btn"):
                    url = storage.get_signed_url(f"{target}/original.zip")
                    if url:
                        st.markdown(f"[🔗 zip 다운로드]({url})")
                    else:
                        st.error("URL 생성 실패")
            with col_b:
                if st.button("📄 result.md 다운로드 URL 생성", key="dl_md_btn"):
                    url = storage.get_signed_url(f"{target}/result.md")
                    if url:
                        st.markdown(f"[🔗 md 다운로드]({url})")
                    else:
                        st.error("URL 생성 실패")

    st.markdown("### 통계")
    total = len(rows) if rows else 0
    if total > 0:
        done = sum(1 for r in rows if r.get("status") == "done")
        fb = sum(1 for r in rows if r.get("used_fallback"))
        avg_pages = sum((r.get("page_count") or 0) for r in rows) / total
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("총 제출", total)
        c2.metric("완료율", f"{done / total * 100:.0f}%")
        c3.metric("평균 페이지", f"{avg_pages:.1f}")
        c4.metric("폴백률", f"{fb / total * 100:.0f}%")
