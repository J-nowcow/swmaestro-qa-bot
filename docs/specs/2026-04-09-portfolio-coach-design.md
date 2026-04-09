# 포트폴리오 코치 설계 문서

- **작성일**: 2026-04-09
- **상태**: 설계 완료, 구현 대기
- **대상 레포**: `J-nowcow/swmaestro-mentee-tools` (구 `swmaestro-qa-bot`)

---

## 1. 개요

### 1.1 목적

SW마에스트로 멘토(현재 사용자)가 멘티들에게 자신의 포트폴리오 평가 철학을 자동화된 도구로 제공한다. 멘티는 Notion에서 export한 포트폴리오 zip을 업로드하면, 멘토가 정의한 10가지 평가 기준에 따른 피드백과 카테고리별 예상 면접 질문을 받는다.

### 1.2 대상 사용자

- **주 사용자**: SW마에스트로 연수생 (취업 준비자 / 창업 희망자 / 진로 미정 모두 포함)
- **운영자(관리자)**: SW마에스트로 멘토 (= 본 도구 제공자)

### 1.3 핵심 가치

- **단일 진입점**: zip 업로드 한 번으로 평가 + 예상 질문 제공
- **멘토 철학 일관성**: 시스템 프롬프트로 멘토의 10가지 기준 고정
- **운영 비용 0원 지향**: Gemini 무료 티어 + Supabase 무료 티어 + Streamlit Cloud
- **확장 옵션**: 사용자가 자기 API 키(BYOK) 입력 시 무료 한도 제약 없음

### 1.4 평가 기준 (10항목)

본 도구가 사용하는 10가지 평가 항목 (멘토의 평가 철학):

1. 첫 화면에서 10초 안에 어떤 개발자인지 보이는가
2. 각 프로젝트가 한 문장으로 설명되는가
3. 내가 한 일과 팀이 한 일이 구분되는가
4. 기술 선택의 이유를 논리적으로 설명할 수 있는가
5. 기술 스택이 너무 많지는 않은가
6. 트러블슈팅은 느낌이 아니라 수치로 말할 수 있는가
7. 문제가 실제로 있었음을 증명할 수 있는가
8. 화면, 캡처, 다이어그램이 설명을 도와주는가
9. 협업 흔적이 보이는가
10. 실패나 한계를 솔직하게 말할 수 있는가

---

## 2. 통합 전략 (기존 레포 재사용)

### 2.1 기존 레포 자산

`swmaestro-mentee-tools` 레포는 현재 SW마에스트로 Q&A RAG 챗봇으로 운영 중이다. 다음 자산을 그대로 재사용한다:

| 자산 | 재사용 방식 |
|---|---|
| Streamlit Cloud 배포 파이프라인 | git push만으로 자동 배포 |
| Gemini API 키 (`GOOGLE_API_KEY`) | Secrets에 이미 등록됨 |
| Supabase 연동 (`SUPABASE_URL`, `SUPABASE_KEY`) | `rag/db.py` 범용 래퍼 그대로 사용 |
| 8-모델 폴백 체인 패턴 (`rag/chain.py`) | `portfolio/llm.py`로 패턴 복제 (멀티모달 지원 추가) |
| 로깅 패턴 (Supabase + 옵셔널 Sheets webhook) | `portfolio_submissions` 테이블에 동일 패턴 적용 |
| 관리자 비밀번호 (`ADMIN_PASSWORD`) | 포트폴리오 관리자 섹션에서도 재사용 |

### 2.2 격리 원칙

- 기존 `app.py`, `rag/`, `scraper/`, `scripts/`, `data/` 디렉토리는 **0줄 수정**한다.
- 신규 코드는 모두 `portfolio/` 디렉토리와 `pages/` 디렉토리에만 작성한다.
- `rag/db.py`는 도메인 종속이 없는 범용 Supabase 래퍼이므로 cross-module 호출을 허용한다.
- 롤백은 신규 파일 삭제만으로 완료된다.

---

## 3. 아키텍처

### 3.1 시스템 구성

```
┌────────────────────────────────────────────────────────────┐
│  Streamlit App                                             │
│                                                            │
│  app.py (기존 Q&A 챗봇 - 변경 없음)                          │
│  pages/2_📋_포트폴리오_코치.py (신규, 진입점)                 │
│         │                                                  │
│         ▼                                                  │
│  portfolio.ui.render()                                     │
│         │                                                  │
│   ┌─────┴─────┬──────────┬──────────┬────────┬──────────┐ │
│   ▼           ▼          ▼          ▼        ▼          ▼ │
│ parser     storage   ratelimit   evaluator question_gen compose
│   │           │          │          │        │          │ │
│   │           │          │          └────┬───┘          │ │
│   │           │          │               │              │ │
│   │           │          │               ▼              │ │
│   │           │          │             llm.py           │ │
│   │           │          │               │              │ │
└───┼───────────┼──────────┼───────────────┼──────────────┼─┘
    ▼           ▼          ▼               ▼              │
 Pillow    Supabase    Supabase        Gemini REST       │
 (이미지)   Storage     Postgres        (8-모델 폴백,     │
            (zip+md)    (rag/db.py)     멀티모달)         │
                                                          ▼
                                                    Streamlit
                                                    렌더링 + 다운로드
```

### 3.2 데이터 흐름 (행복 경로)

1. 사용자가 포트폴리오 페이지 진입 → `pages/2_📋_포트폴리오_코치.py` → `portfolio.ui.render()`
2. zip 업로드 (`st.file_uploader`, ≤20MB)
3. 동의 체크박스 확인 → "분석 시작" 클릭
4. **검증 단계**
   - IP 해시 계산 → `portfolio.ratelimit.check_ip_limit()` (일 5회)
   - BYOK 미사용 시 일일 RPD 확인 → `portfolio.ratelimit.check_daily_rpd()` (일 240회)
5. **파싱 단계**
   - `portfolio.parser.parse_notion_zip(zip_bytes)` → `ParsedPortfolio`
   - `.md` 결합, Notion id 접미사 제거, 이미지 첫 30장 base64 인코딩(Pillow 1024px 리사이즈)
6. **저장 단계 (best-effort)**
   - `portfolio.storage.upload_submission(zip, ...)` → Supabase Storage
   - `portfolio_submissions` row 인서트 (메타데이터)
7. **LLM 호출 1: 평가**
   - `portfolio.evaluator.evaluate(parsed, llm_client)` → `EvaluationResult`
   - 멀티모달 (텍스트 + 이미지)
   - 8-모델 폴백, 멀티모달 미지원 모델은 이미지 제거 후 텍스트만으로 시도
8. **LLM 호출 2: 면접 질문**
   - `portfolio.question_gen.generate(parsed, evaluation, llm_client)` → `QuestionResult`
   - 텍스트 전용 (이미지 재전송 X, 토큰 절약)
9. **결과 조립**
   - `portfolio.compose_md.compose_result_md(evaluation, questions, meta)` → `str` (마크다운)
10. **결과 저장 (best-effort)**
    - 같은 Storage 폴더에 `result.md` 추가
    - `portfolio_submissions` row 업데이트 (`eval_summary`, `tokens_*`, `model_used`)
11. **사용자에게 표시**
    - `st.markdown(result_md)` 한 페이지 렌더링
    - `st.download_button`으로 MD 다운로드 제공

### 3.3 데이터 흐름 (에러 경로)

| 실패 지점 | 사용자 경험 | 시스템 동작 |
|---|---|---|
| IP/RPD 한도 초과 | 친절 메시지 + BYOK 안내 | 카운터 미증가, 분석 중단 |
| zip 파싱 실패 | "Notion zip이 맞는지 확인" | 카운터 미증가, 분석 중단 |
| Storage 저장 실패 | **사용자에게는 노출 X** | stderr 로그, 분석은 계속 진행 |
| LLM Call 1 실패 (8-모델 모두) | "일시 장애, 잠시 후 재시도" | 카운터는 증가 상태 유지(어뷰즈 방지) |
| LLM Call 2 실패 | Call 1 결과만 표시 + 경고 | best-effort, 평가는 정상 노출 |
| MD 저장 실패 | **사용자에게는 노출 X** | stderr 로그, 사용자 다운로드는 정상 |

---

## 4. 모듈 설계

### 4.1 디렉토리 구조

```
swmaestro-mentee-tools/  (로컬 경로: ~/Desktop/개발/swmaestro-qa-bot)
├── app.py                              ← 변경 없음
├── rag/                                ← 변경 없음
├── pages/                              ← 신규
│   └── 2_📋_포트폴리오_코치.py          ← 진입점
├── portfolio/                          ← 신규 디렉토리
│   ├── __init__.py
│   ├── ui.py                           ← Streamlit 사용자 페이지
│   ├── admin.py                        ← 관리자 섹션 (페이지 하단)
│   ├── parser.py                       ← zip → ParsedPortfolio
│   ├── prompts.py                      ← 시스템 프롬프트 + JSON 스키마
│   ├── llm.py                          ← Gemini 멀티모달 호출 + 폴백
│   ├── evaluator.py                    ← Call 1: 10항목 평가
│   ├── question_gen.py                 ← Call 2: 카테고리별 질문
│   ├── compose_md.py                   ← 결과 → 마크다운
│   ├── storage.py                      ← Supabase Storage 래퍼
│   └── ratelimit.py                    ← IP/일일 카운터
├── tests/
│   └── portfolio/                      ← 신규
│       ├── test_parser.py
│       ├── test_compose_md.py
│       ├── test_ratelimit.py
│       ├── test_prompts.py
│       └── fixtures/
│           └── sample-notion-export.zip
├── migrations/                         ← 신규
│   └── 2026-04-09-portfolio.sql
└── requirements.txt                    ← Pillow 추가
```

### 4.2 모듈별 책임

#### `portfolio/parser.py`

**책임**: Notion 마크다운 export zip을 파싱하여 텍스트와 이미지로 분리.

**핵심 함수**:
```python
def parse_notion_zip(zip_bytes: bytes) -> ParsedPortfolio
```

**동작**:
- Python `zipfile` 표준 라이브러리 사용
- `.md` 파일을 알파벳순으로 결합
- Notion 페이지 id (32자 hex) 접미사 제거: `"About abc123def456..."` → `"About"`
- 이미지: 첫 30장만 추출, Pillow로 1024px 리사이즈, base64 인코딩
- 30장 초과 시 `truncated=True` 표시
- 4MB 이상 단일 이미지는 스킵

**반환**:
```python
@dataclass
class ParsedPortfolio:
    markdown: str
    images: list[ImageData]   # [{filename, mime_type, base64, original_index}]
    stats: PortfolioStats     # {page_count, image_count, image_truncated, total_chars}
```

**예외**:
- `InvalidZipError`: zip 형식 아님 / 손상
- `NoMarkdownError`: zip 안에 .md 파일 0개
- `ZipTooLargeError`: 압축 해제 후 50MB 초과 (zip bomb 방지)

---

#### `portfolio/prompts.py`

**책임**: 시스템 프롬프트와 JSON 스키마 정의.

**상수**:
- `SYSTEM_PROMPT_EVALUATOR`: 10항목 철학 + 페르소나 (한국어)
- `SYSTEM_PROMPT_QUESTIONS`: 카테고리별 질문 생성 지침
- `EVALUATION_SCHEMA`: Gemini structured output용 JSON 스키마
- `QUESTIONS_SCHEMA`: 동일

**페르소나 (`SYSTEM_PROMPT_EVALUATOR` 핵심)**:
> 당신은 SW마에스트로 연수생의 포트폴리오를 평가하는 시니어 면접관입니다. 연수생은 취업 준비자, 창업 희망자, 진로 미정자 등 다양하므로 진로를 단정하지 마세요. 아래 10가지 기준에 따라 평가하고, 각 항목마다 1~5점 점수와 구체적 근거를 제시하세요.

**카테고리 매핑 (질문 생성용)**:
1. 자기소개 / 첫인상 — 항목 1, 2
2. 기여도 명확성 — 항목 3
3. 기술 의사결정 — 항목 4, 5
4. 트러블슈팅 / 정량화 — 항목 6, 7
5. 협업 / 한계 인식 — 항목 9, 10

(항목 8은 평가에만 반영, 질문 카테고리는 아님)

---

#### `portfolio/llm.py`

**책임**: Gemini REST API 호출 + 8-모델 폴백 + 멀티모달 지원.

**핵심 함수**:
```python
def call_multimodal(
    system_prompt: str,
    user_text: str,
    images: list[ImageData] | None = None,
    response_schema: dict | None = None,
    api_key: str | None = None,        # BYOK 지원
    status_callback: Callable | None = None,
) -> tuple[str, str, dict]:
    """
    Returns:
        (response_text, model_used, token_usage)
    """
```

**구현 세부**:
- `rag/chain.py:_call_gemini` 패턴 복제
- `parts`에 `text` + `inline_data` (base64 이미지) 포함
- 모델 순서:
  - **MM_MODELS** (멀티모달 우선): `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-flash-latest`
  - **TEXT_FALLBACK** (모두 실패 시 이미지 제거): `gemini-2.5-flash-lite`, `gemini-2.0-flash-lite`, `gemini-flash-lite-latest`
- 429 → 다음 모델
- 5xx → 다음 모델
- response_schema 있으면 `generationConfig.responseSchema` 추가
- 모두 실패 → `LLMUnavailableError`

**BYOK 동작**:
- `api_key` 인자 전달되면 그것 사용, 아니면 `os.getenv("GOOGLE_API_KEY")`
- 사용자가 Anthropic 키 입력한 경우는 v1 범위 외 (Gemini 키만 BYOK 지원). v1.1에서 Anthropic 분기 추가 검토.

---

#### `portfolio/evaluator.py`

**책임**: Call 1 — 10항목 평가 수행.

```python
def evaluate(
    parsed: ParsedPortfolio,
    api_key: str | None = None,
    status_callback: Callable | None = None,
) -> EvaluationResult
```

- `prompts.SYSTEM_PROMPT_EVALUATOR` + `parsed.markdown` + `parsed.images` 전달
- `prompts.EVALUATION_SCHEMA`로 structured output 강제
- 실패 시 `LLMUnavailableError` 전파

**반환**:
```python
@dataclass
class EvaluationResult:
    overall: dict          # {one_liner, strengths: [3], weaknesses: [3]}
    criteria: list[dict]   # 10개 [{id, title, score, evaluation, evidence}]
    model_used: str
    tokens: dict           # {input, output}
```

---

#### `portfolio/question_gen.py`

**책임**: Call 2 — 카테고리별 면접 질문 생성.

```python
def generate(
    parsed: ParsedPortfolio,
    evaluation: EvaluationResult,
    api_key: str | None = None,
    status_callback: Callable | None = None,
) -> QuestionResult
```

- 입력: 평가 결과(약점 위주) + 마크다운 (이미지 X)
- `prompts.SYSTEM_PROMPT_QUESTIONS` + `prompts.QUESTIONS_SCHEMA`
- 카테고리 5개 고정

**반환**:
```python
@dataclass
class QuestionResult:
    categories: list[dict]   # [{name, questions: list[str], rationale}]
    model_used: str
    tokens: dict
```

---

#### `portfolio/compose_md.py`

**책임**: 평가 결과 + 질문 결과 → 단일 마크다운 페이지 조립.

```python
def compose_result_md(
    evaluation: EvaluationResult,
    questions: QuestionResult | None,  # None 허용 (Call 2 실패 케이스)
    metadata: dict,
) -> str
```

**출력 구조**:
```markdown
# 포트폴리오 평가 결과

> 분석 일시: 2026-04-09 15:42 KST
> 사용 모델: gemini-2.5-flash

## 📊 종합 평가
**한 줄 총평**: ...

**강점**
- ...
- ...
- ...

**약점**
- ...
- ...
- ...

## 📝 10항목 상세 평가

### 1. 첫 화면에서 10초 안에 어떤 개발자인지 보이는가
⭐⭐⭐ (3/5)

**평가**: ...

**근거**: ...

### 2. ...
(10개 반복)

## 🎤 예상 면접 질문

### 1. 자기소개 / 첫인상
- Q: ...
- Q: ...

### 2. 기여도 명확성
...
(5개 카테고리)

## 📌 분석 노트
- 페이지 수: 12
- 이미지 수: 23 (전부 분석 포함)
- 모델: gemini-2.5-flash
```

---

#### `portfolio/storage.py`

**책임**: Supabase Storage REST API 래퍼 (SDK 미사용).

**핵심 함수**:
```python
def upload_file(bucket: str, path: str, content: bytes, content_type: str) -> bool
def download_file(bucket: str, path: str) -> bytes | None
def get_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str | None
def list_files(bucket: str, prefix: str = "") -> list[dict]
```

**고수준 함수**:
```python
def upload_submission(
    zip_bytes: bytes,
    metadata: dict,
) -> SubmissionRef:
    """zip 업로드 + DB row 생성. 결과 MD는 나중에 별도 저장"""

def attach_result_md(submission_id: str, result_md: str, eval_summary: str) -> None:
    """평가 완료 후 result.md 추가 + DB row 업데이트"""
```

**경로 규칙**:
```
portfolio-uploads/                          ← 버킷 (private)
└── {YYYYMMDD}/{timestamp}-{random6}/
    ├── original.zip
    ├── result.md                           ← Call 1+2 완료 후 추가
    └── meta.json
```

**환경변수**: 기존 `SUPABASE_URL`, `SUPABASE_KEY` 재사용. 신규 환경변수 없음.

---

#### `portfolio/ratelimit.py`

**책임**: IP 단위 + 전역 일일 카운터 관리.

**핵심 함수**:
```python
def hash_ip(raw_ip: str) -> str:
    """SHA256(ip + IP_HASH_SALT). salt는 환경변수, 미설정 시 기본값 사용"""

def check_and_increment_ip(ip_hash: str) -> RateLimitStatus:
    """IP 한도 체크 + 통과 시 카운트 증가 (atomic)"""

def check_and_increment_rpd(num_calls: int = 2, byok: bool = False) -> tuple[bool, int]:
    """일일 RPD 체크. byok=True면 미카운트하고 (True, remaining) 반환"""

def get_today_status() -> dict:
    """사이드바 표시용: {daily_used, daily_cap, today: 'YYYY-MM-DD'}"""
```

**Streamlit 사용자 IP 획득**:
- Streamlit Cloud는 직접 제공 안 함 → `st.context.headers.get("x-forwarded-for")` 시도 (Streamlit 1.40+)
- 미지원 환경에서는 `session_id`를 IP 대용으로 사용 (heuristic)

---

#### `portfolio/ui.py`

**책임**: Streamlit 사용자 페이지 본문.

**핵심 함수**:
```python
def render() -> None
```

**섹션**:
1. 사이드바 (사용법 + 한도 표시)
2. 헤더 + 설명
3. 파일 업로더 (`st.file_uploader`)
4. zip 미리보기 (페이지 수, 이미지 수, 텍스트 크기)
5. 고급 설정 expander (BYOK 입력)
6. 동의 체크박스
7. 분석 시작 버튼
8. 진행 단계 (`st.status` 컨테이너)
9. 결과 표시 + 다운로드 버튼
10. 페이지 하단: `portfolio.admin.render()` 호출

**세션 상태 키**:
- `pf_uploaded_zip`: bytes
- `pf_parsed`: ParsedPortfolio | None
- `pf_consent`: bool
- `pf_byok_key`: str
- `pf_progress`: dict (각 단계 상태)
- `pf_result_md`: str | None
- `pf_error`: str | None

---

#### `portfolio/admin.py`

**책임**: 관리자 섹션 (페이지 하단, 비번 보호).

**핵심 함수**:
```python
def render() -> None
```

- 비번 입력 → 일치 시 (`os.getenv("ADMIN_PASSWORD")` 재사용) 대시보드 표시
- 제출 목록 (최근 50건, 페이지네이션)
- 각 행: 시간, 페이지/이미지 수, 모델, fallback 여부, [zip 다운로드] [md 다운로드] 버튼
- 통계 카드: 총 제출, 평균 페이지 수, 평균 이미지 수, 폴백률

---

### 4.3 신규 진입점 파일

#### `pages/2_📋_포트폴리오_코치.py`

```python
"""SW마에스트로 포트폴리오 코치"""
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
```

20줄 이내. 모든 로직은 `portfolio/` 하위 모듈에.

---

## 5. 데이터 모델

### 5.1 Supabase Postgres 스키마 (신규 3개 테이블)

```sql
-- 1. 제출 기록 (전체 히스토리)
CREATE TABLE portfolio_submissions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    ip_hash         text NOT NULL,
    storage_path    text NOT NULL,
    file_size       int NOT NULL,
    page_count      int,
    image_count     int,
    image_truncated boolean DEFAULT false,
    model_used      text,
    used_byok       boolean DEFAULT false,
    used_fallback   boolean DEFAULT false,
    tokens_input    int,
    tokens_output   int,
    eval_summary    text,
    status          text NOT NULL DEFAULT 'pending',  -- pending|done|error
    error           text
);
CREATE INDEX idx_portfolio_submissions_created ON portfolio_submissions(created_at DESC);
CREATE INDEX idx_portfolio_submissions_ip ON portfolio_submissions(ip_hash);

-- 2. IP 단위 rate limit (KST 일 단위)
CREATE TABLE portfolio_ratelimit (
    ip_hash         text NOT NULL,
    window_date     date NOT NULL,
    count           int NOT NULL DEFAULT 0,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ip_hash, window_date)
);

-- 3. 일일 RPD 카운터 (전역)
CREATE TABLE portfolio_daily_count (
    date            date PRIMARY KEY,
    count           int NOT NULL DEFAULT 0,
    cap             int NOT NULL DEFAULT 240
);
```

마이그레이션 SQL은 `migrations/2026-04-09-portfolio.sql`에 커밋.

### 5.2 Supabase Storage 버킷

```
portfolio-uploads/                          ← private 버킷
└── {YYYYMMDD}/{HHMMSS}-{random6}/
    ├── original.zip
    ├── result.md
    └── meta.json
```

- 정책: private (관리자만 signed URL 발급으로 접근)
- 정리: v1에서는 무제한 보관. 1GB 도달 시 관리자 대시보드에서 수동 정리.

---

## 6. UI / 사용자 흐름

### 6.1 페이지 진입 (초기 상태)

**사이드바**:
- 페이지 제목 + 한 줄 설명
- 사용법 (1) Notion → ⋯ → Export, (2) Markdown & CSV, (3) zip 업로드
- 오늘의 한도 라이브 표시:
  - "무료 분석: {daily_used} / 240"
  - "본인 분석: {ip_used} / 5"

**메인**:
- 헤더: "📋 포트폴리오 코치"
- 설명 한 줄
- 드래그앤드롭 영역
- 고급 설정 expander (BYOK 입력)
- 동의 체크박스 (필수)
- 분석 시작 버튼 (체크박스 미체크 시 비활성화)

### 6.2 zip 업로드 직후 (미리보기)

zip을 받으면 즉시 파싱 → 미리보기 표시 (LLM 호출 전):
- 페이지 수 (".md 파일 수)
- 이미지 수 ("23개 이미지 감지, 전부 분석 포함" 또는 "47개 → 첫 30장만 분석")
- 텍스트 분량 ("약 8,400자")

### 6.3 분석 진행 중

`st.status` 컨테이너로 단계별 표시:
1. ✅ zip 파싱 완료
2. ✅ 파일 보관 완료
3. 🔄 10항목 평가 중... (약 30초)
4. ⏸ 예상 면접 질문 생성 대기

폴백 발생 시 `st.warning("요청이 많아 대체 모델로 시도 중...")` 표시.

### 6.4 결과 표시

- `st.markdown(result_md)` 한 페이지 렌더링
- 우상단: [📥 MD 다운로드] [↻ 새로 분석] 버튼
- 다운로드 파일명: `portfolio-review-{YYYYMMDD-HHMMSS}.md`

### 6.5 에러 케이스

| 상황 | 메시지 |
|---|---|
| IP 한도 초과 | "오늘은 더 이상 분석할 수 없습니다. 내일 다시 시도하거나 본인 API 키를 입력해주세요." + BYOK 안내 |
| 일일 RPD 한도 초과 | "오늘 무료 분석 한도가 소진되었습니다. 본인 API 키 입력 시 즉시 사용 가능합니다." + BYOK 안내 |
| zip 파싱 실패 | "zip 파일을 읽을 수 없습니다. Notion에서 'Markdown & CSV' 형식으로 export했는지 확인해주세요." |
| .md 파일 0개 | "zip 안에 마크다운 파일이 없습니다." |
| 모든 모델 폴백 실패 | "현재 LLM 서비스에 일시적 문제가 있습니다. 잠시 후 다시 시도해주세요." |
| BYOK 키 인증 실패 | "API 키 인증에 실패했습니다. 키가 올바른지 확인해주세요." |

### 6.6 관리자 섹션

페이지 하단에 expander로 추가:
- 비밀번호 입력 (`ADMIN_PASSWORD` 재사용)
- 인증 후: 제출 목록 테이블 + 통계 카드

---

## 7. Rate Limit 정책

### 7.1 IP 단위

- 키: `SHA256(ip + IP_HASH_SALT)`
- 윈도우: KST 자정 기준 일 단위
- 한도: **5회/일**
- 카운트 시점: 분석 시작 직전 (파싱 전)
- 실패 시 환불: 없음 (어뷰즈 방지)
- BYOK: **카운트 X**

### 7.2 일일 RPD (전역)

- 키: 오늘 KST 날짜
- 한도: **240회/일** (Gemini 250 RPD에서 안전마진 10)
- 카운트 단위: Gemini API 호출 1건 (Call 1, Call 2 각각 +1 → 분석 1회 = +2)
- BYOK: **카운트 X**
- 자정 자동 리셋 (UPSERT로 새 row 생성)

### 7.3 폴백 체인 효과

8-모델 폴백을 사용하므로 실효 RPD는 Gemini 1차 모델 250 + 폴백 모델 250 × 7 ≈ **이론상 2000 RPD**까지 확장 가능. 다만 동일 프로젝트에서 모델별 쿼터가 공유될 수 있으므로 보수적으로 240 cap 유지.

---

## 8. 에러 처리 / 운영

### 8.1 계층별 책임

| 계층 | 정책 |
|---|---|
| UI 검증 | 즉시 차단, 친절한 메시지 |
| 파싱 | 커스텀 예외 → UI에서 변환 |
| LLM 호출 | 8-모델 폴백, 모두 실패 시 `LLMUnavailableError` |
| Storage / DB 저장 | **best-effort** (사용자에게 노출 X, stderr 로그) |

### 8.2 로깅

- `print("[PORTFOLIO] ...", flush=True)` → Streamlit Cloud logs
- `db.insert("portfolio_submissions", ...)` → Supabase
- 옵셔널: `LOG_WEBHOOK_URL` 있으면 Google Sheets 백업 (기존 패턴)

### 8.3 메트릭 (관리자 대시보드)

```sql
-- 최근 30일 일별 제출 수
SELECT date_trunc('day', created_at) AS day, count(*)
FROM portfolio_submissions
WHERE created_at > now() - interval '30 days'
GROUP BY 1 ORDER BY 1;

-- 모델 사용 분포
SELECT model_used, count(*) FROM portfolio_submissions GROUP BY 1;

-- 평균 페이지/이미지
SELECT avg(page_count), avg(image_count) FROM portfolio_submissions;

-- 폴백 사용률
SELECT
  count(*) FILTER (WHERE used_fallback) * 100.0 / count(*) AS fallback_pct
FROM portfolio_submissions;
```

### 8.4 배포 / 롤백

| 항목 | 처리 |
|---|---|
| 배포 | git push → Streamlit Cloud 자동 배포 |
| DB 마이그레이션 | Supabase 콘솔에서 `migrations/2026-04-09-portfolio.sql` 실행 (테이블 3개 + Storage 버킷 1개) |
| 롤백 | `pages/2_📋_포트폴리오_코치.py` 삭제 → 메뉴에서 사라짐. 기존 Q&A 영향 0 |
| 점진 배포 | (옵션) 페이지 상단에 비번 입력 expander 추가 → 멘토만 접근 가능한 v0 단계 |

---

## 9. 개인정보 / 보안

| 항목 | 처리 |
|---|---|
| IP 주소 | SHA256 해시만 저장. raw IP는 어디에도 안 남김 |
| 포트폴리오 zip | Supabase Storage 보관 (멘토 분석 목적). 사용자 동의 체크박스 필수 |
| 평가 결과 MD | zip과 같은 폴더에 보관 |
| BYOK API 키 | 메모리에서만 사용, 어디에도 저장 X (DB/Storage/로그 모두) |
| 재학생 PII (이름/이메일 등) | zip 안에 포함 가능 → 동의 화면에 명시 |
| 삭제 요청 | v1: 멘토 수동 처리. v1.1: 자동화 검토 |

---

## 10. 테스트 전략

### 10.1 유닛 테스트 (`tests/portfolio/`)

| 파일 | 검증 대상 |
|---|---|
| `test_parser.py` | Notion id 접미사 제거, 30장 cap, 빈 zip / md 0개 / 손상 zip 에러, zip bomb 차단 |
| `test_compose_md.py` | EvaluationResult + QuestionResult → 마크다운 형식, Question 결과 None 케이스 |
| `test_ratelimit.py` | IP 카운터 증감, 윈도우 경계, BYOK 미카운트 |
| `test_prompts.py` | 시스템 프롬프트에 10항목 모두 포함 (regression 방지) |

LLM 호출 (`evaluator.py`, `question_gen.py`)은 모킹하여 실제 Gemini 미호출.

### 10.2 통합 테스트 (수동)

- 픽스처: `tests/portfolio/fixtures/sample-notion-export.zip` (3페이지 + 2이미지, PII 0)
- 로컬 `streamlit run app.py` → 새 페이지 진입 → 업로드 → 결과 확인
- 멘토 본인의 실제 포트폴리오 zip으로 1회 end-to-end 검증

### 10.3 회귀 방지

- 기존 Q&A 페이지가 변경 없이 동작하는지 (배포 후 1회 수동 확인)
- `app.py` diff = 0 임을 PR 시 확인

---

## 11. 비용 추정

| 항목 | 무료 한도 | 예상 사용량 (일) | 여유 |
|---|---|---|---|
| Gemini API | 250 RPD × 8모델 폴백 | 100명 × 2호출 = 200 | ✅ |
| Supabase Storage | 1GB | zip 평균 2MB × 500건 = 1GB | ⚠️ 1년 내 도달 가능 |
| Supabase Postgres | 500MB | 메타데이터만 | ✅ |
| Streamlit Cloud | 1GB RAM | Pillow 처리 OK | ✅ |

**Storage 1GB 도달 시 대응**: 관리자 대시보드에 "오래된 zip 일괄 삭제" 버튼 추가 (v1.1).

---

## 12. 확장 / Out-of-Scope

### 12.1 v1 범위 (이번 spec)

- Notion zip 업로드 → 평가 + 면접 질문 → MD 다운로드
- Gemini Flash 기본, BYOK Gemini 키 지원
- 멘토 관리자 대시보드 (제출 목록 + 통계)
- IP rate limit + 일일 RPD limit

### 12.2 v1.1 (가까운 미래)

- BYOK Anthropic 키 지원 (`portfolio/llm.py`에 Anthropic 분기 추가)
- 관리자 대시보드 "오래된 zip 일괄 삭제" 버튼
- 사용자 삭제 요청 자동 처리

### 12.3 v2 (장기)

- 평가 결과에 개선 제안 추가 (rewrite 예시)
- 인터랙티브 모의 면접 (사용자 답변 → 후속 질문)
- 사용자 계정 (로그인 시 본인 과거 평가 다시 보기)
- 직군별 페르소나 분기 (백엔드/프론트/AI/임베디드)

---

## 13. 의사결정 기록

| # | 결정 | 이유 |
|---|---|---|
| 1 | 별도 레포 X, 기존 `swmaestro-mentee-tools`에 통합 | 인프라 100% 재사용, 운영 부담 0 |
| 2 | Streamlit multipage (`pages/`) 사용, tab 추가 X | URL/상태/사이드바 완전 격리 |
| 3 | 기존 코드 0줄 수정 | 롤백 안전, 회귀 위험 0 |
| 4 | `rag/db.py` 재사용 (cross-module) | 도메인 종속 없는 범용 래퍼 |
| 5 | `portfolio/llm.py`로 Gemini 호출 패턴 복제 (refactor X) | 멀티모달 추가 + 격리 우선 |
| 6 | LLM 2단계 호출 (평가 → 질문) | 분리하면 둘 다 깊이 향상, 평가가 질문의 컨텍스트 |
| 7 | 이미지 30장 cap | 무료 티어 안전 + 평균 포트폴리오 커버 가능 |
| 8 | Call 2에서 이미지 재전송 X | 토큰 절약, 평가 결과가 충분한 컨텍스트 |
| 9 | IP 단위 5회/일, 전역 240/일 | 어뷰즈 방지 + 무료 한도 안전마진 |
| 10 | best-effort 저장 | UX > 데이터 완전성 (멘토 분석은 보조 가치) |
| 11 | SDK 미사용, 순수 `requests` | 기존 패턴 일관성, 의존성 최소화 |
