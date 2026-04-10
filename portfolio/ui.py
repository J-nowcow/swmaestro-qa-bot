"""Streamlit user-facing portfolio coach page."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import streamlit as st

from portfolio import ratelimit, storage
from portfolio.compose_md import compose_result_md
from portfolio.evaluator import EvaluatorError, evaluate
from portfolio.llm import LLMUnavailableError
from portfolio.parser import (
    InvalidZipError,
    NoMarkdownError,
    ParsedPortfolio,
    ZipTooLargeError,
    parse_notion_zip,
)
from portfolio.question_gen import QuestionGenError, generate as generate_questions

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
SESSION_PREFIX = "pf_"


def _kst_now_str() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")


def _client_ip() -> str:
    """Best-effort IP retrieval. Falls back to session_id when unavailable."""
    try:
        headers = st.context.headers  # type: ignore[attr-defined]
        xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    except Exception:
        pass
    sid = st.session_state.get("pf_session_id")
    if not sid:
        import uuid
        sid = str(uuid.uuid4())
        st.session_state.pf_session_id = sid
    return f"session:{sid}"


def _init_state() -> None:
    defaults = {
        "pf_uploaded_bytes": None,
        "pf_uploaded_name": None,
        "pf_parsed": None,
        "pf_byok_key": "",
        "pf_result_md": None,
        "pf_error": None,
        "pf_meta": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_sidebar(ip_hash: str) -> None:
    st.sidebar.markdown("## 📋 포트폴리오 코치")
    st.sidebar.markdown(
        "SW마에스트로 멘토의 평가 철학으로\n포트폴리오를 자동 피드백받기"
    )
    st.sidebar.divider()
    st.sidebar.markdown("**사용법**")
    st.sidebar.markdown(
        "1. Notion 페이지 열기\n"
        "2. ⋯ 메뉴 → Export\n"
        "3. **Markdown & CSV** 선택\n"
        "4. zip 파일 업로드"
    )
    st.sidebar.divider()
    st.sidebar.markdown("**오늘의 한도**")
    daily = ratelimit.get_today_status()
    ipst = ratelimit.get_ip_status(ip_hash)
    st.sidebar.markdown(
        f"- 무료 분석: **{daily['daily_used']} / {daily['daily_cap']}**\n"
        f"- 본인 분석: **{ipst['ip_used']} / {ipst['ip_limit']}**"
    )
    st.sidebar.caption("BYOK(본인 키) 사용 시 카운트되지 않습니다.")


def _try_parse_uploaded(zip_bytes: bytes) -> ParsedPortfolio | None:
    try:
        return parse_notion_zip(zip_bytes)
    except InvalidZipError:
        st.session_state.pf_error = "zip 파일을 읽을 수 없습니다. Notion에서 'Markdown & CSV' 형식으로 export했는지 확인해주세요."
    except NoMarkdownError:
        st.session_state.pf_error = "zip 안에 마크다운 파일이 없습니다."
    except ZipTooLargeError:
        st.session_state.pf_error = "압축을 풀었을 때 50MB를 초과합니다. 파일 수를 줄여주세요."
    return None


def _run_analysis(
    parsed: ParsedPortfolio,
    api_key: str | None,
    ip_hash: str,
) -> None:
    used_byok = bool(api_key)

    # Rate limit checks
    ip_status = ratelimit.check_and_increment_ip(ip_hash)
    if not ip_status.allowed:
        st.session_state.pf_error = (
            "오늘은 더 이상 분석할 수 없습니다. 내일 다시 시도하거나 본인 API 키를 입력해주세요."
        )
        return

    rpd_ok, _ = ratelimit.check_and_increment_rpd(num_calls=2, byok=used_byok)
    if not rpd_ok:
        st.session_state.pf_error = (
            "오늘 무료 분석 한도가 소진되었습니다. 본인 API 키 입력 시 즉시 사용 가능합니다."
        )
        return

    progress = st.status("분석 중...", expanded=True)
    progress.write("✅ zip 파싱 완료")

    # Best-effort: save submission
    submission = storage.upload_submission(
        zip_bytes=st.session_state.pf_uploaded_bytes,
        ip_hash=ip_hash,
        file_size=len(st.session_state.pf_uploaded_bytes),
        page_count=parsed.stats.page_count,
        image_count=parsed.stats.image_count,
        image_truncated=parsed.stats.image_truncated,
    )
    storage_path = submission["storage_path"]
    progress.write("✅ 파일 보관 완료")

    def _on_status(msg: str) -> None:
        progress.write(f"⚠️ {msg}")

    # Call 1: evaluation
    progress.write("🔄 10항목 평가 중...")
    try:
        ev = evaluate(parsed, api_key=api_key, status_callback=_on_status)
    except (LLMUnavailableError, EvaluatorError) as e:
        progress.update(state="error", label="평가 실패")
        storage.mark_error(storage_path, f"evaluator: {e}")
        st.session_state.pf_error = (
            "현재 LLM 서비스에 일시적 문제가 있습니다. 잠시 후 다시 시도해주세요."
        )
        return
    progress.write("✅ 10항목 평가 완료")

    # Call 2: questions
    progress.write("🔄 예상 면접 질문 생성 중...")
    used_fallback = ev.model_used != "gemini-2.5-flash"
    qs = None
    try:
        qs = generate_questions(parsed, ev, api_key=api_key, status_callback=_on_status)
    except (LLMUnavailableError, QuestionGenError) as e:
        progress.write(f"⚠️ 질문 생성 실패: {e} — 평가만 표시합니다.")
    else:
        progress.write("✅ 예상 면접 질문 완료")

    # Compose result
    meta = {
        "timestamp": _kst_now_str(),
        "model_used": ev.model_used,
        "page_count": parsed.stats.page_count,
        "image_count": parsed.stats.image_count,
        "image_truncated": parsed.stats.image_truncated,
    }
    result_md = compose_result_md(
        evaluation={"overall": ev.overall, "criteria": ev.criteria},
        questions={"categories": qs.categories} if qs else None,
        metadata=meta,
    )

    # Best-effort: save result
    eval_summary = ev.overall.get("one_liner", "")
    tokens_in = ev.tokens.get("input", 0) + (qs.tokens.get("input", 0) if qs else 0)
    tokens_out = ev.tokens.get("output", 0) + (qs.tokens.get("output", 0) if qs else 0)
    storage.attach_result_md(
        storage_path=storage_path,
        result_md=result_md,
        eval_summary=eval_summary,
        model_used=ev.model_used,
        used_byok=used_byok,
        used_fallback=used_fallback,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
    )

    st.session_state.pf_result_md = result_md
    st.session_state.pf_meta = meta
    progress.update(state="complete", label="✓ 분석 완료")


def _render_uploader(ip_hash: str) -> None:
    st.markdown("# 📋 포트폴리오 코치")
    st.markdown("멘토의 10가지 평가 기준으로 자동 피드백을 받아보세요.")

    uploaded = st.file_uploader(
        "Notion zip 파일을 끌어다 놓거나 클릭해서 선택 (최대 20MB)",
        type=["zip"],
        accept_multiple_files=False,
    )
    if uploaded is not None:
        if uploaded.size > MAX_UPLOAD_BYTES:
            st.error("파일이 20MB를 초과합니다.")
            return
        zip_bytes = uploaded.read()
        st.session_state.pf_uploaded_bytes = zip_bytes
        st.session_state.pf_uploaded_name = uploaded.name
        st.session_state.pf_parsed = _try_parse_uploaded(zip_bytes)

    parsed = st.session_state.pf_parsed
    if parsed is not None:
        with st.container(border=True):
            st.markdown(f"📦 **{st.session_state.pf_uploaded_name}**")
            st.markdown(f"- 페이지 수: {parsed.stats.page_count}")
            if parsed.stats.image_truncated:
                st.warning(
                    f"⚠️ {parsed.stats.image_count}개 이미지 감지 → 첫 30장만 분석에 포함됩니다"
                )
            else:
                st.markdown(
                    f"- 이미지 수: {parsed.stats.image_count} (전부 분석에 포함됨)"
                )
            st.markdown(f"- 텍스트 약 {parsed.stats.total_chars:,}자")

    with st.expander("⚙️ 고급 설정 (선택사항)"):
        st.session_state.pf_byok_key = st.text_input(
            "본인 Google Gemini API 키 (선택)",
            type="password",
            value=st.session_state.pf_byok_key,
            help="키는 이 요청에만 사용되며 어디에도 저장되지 않습니다.",
        )

    can_start = parsed is not None
    if st.button("분석 시작", type="primary", disabled=not can_start):
        st.session_state.pf_error = None
        st.session_state.pf_result_md = None
        api_key = st.session_state.pf_byok_key.strip() or None
        _run_analysis(parsed, api_key=api_key, ip_hash=ip_hash)
        st.rerun()


def _render_result() -> None:
    md = st.session_state.pf_result_md
    if md is None:
        return
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("↻ 새로 분석"):
            for k in ("pf_uploaded_bytes", "pf_uploaded_name", "pf_parsed", "pf_result_md", "pf_meta", "pf_error"):
                st.session_state[k] = None
            st.rerun()
    with col2:
        ts = (st.session_state.pf_meta or {}).get("timestamp", "result").replace(" ", "-").replace(":", "")
        st.download_button(
            label="📥 MD 다운로드",
            data=md,
            file_name=f"portfolio-review-{ts}.md",
            mime="text/markdown",
        )
    st.divider()
    st.markdown(md)


def render() -> None:
    _init_state()
    ip_hash = ratelimit.hash_ip(_client_ip())
    _render_sidebar(ip_hash)

    if st.session_state.pf_result_md is not None:
        _render_result()
    else:
        _render_uploader(ip_hash)
        if st.session_state.pf_error:
            st.error(st.session_state.pf_error)

