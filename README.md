# SW마에스트로 멘티 도구 (SWM Mentee Tools)

[![GitHub stars](https://img.shields.io/github/stars/J-nowcow/swmaestro-mentee-tools?style=social)](https://github.com/J-nowcow/swmaestro-mentee-tools)

> 🌐 **Live demo**: **[swm-mentee-tools.streamlit.app](https://swm-mentee-tools.streamlit.app)**

SW마에스트로 멘티들을 위한 도구 모음입니다. Streamlit으로 제작된 단일 웹앱이며, 두 가지 기능을 제공합니다.

도움이 되셨다면 ⭐ **GitHub 스타**를 눌러주세요!

## 기능

### 📋 포트폴리오 코치 (메인)

Notion에서 export한 포트폴리오 zip을 업로드하면, 엑스퍼트의 평가 철학(10가지 항목)에 따른 자동 피드백과 카테고리별 예상 면접 질문을 생성합니다.

- Gemini Flash 멀티모달 (텍스트 + 이미지 함께 분석)
- 8-모델 폴백 체인으로 무료 한도 안에서 안정 동작
- 결과 마크다운 다운로드
- IP 단위 일일 한도 + 전역 RPD 카운터로 어뷰즈 방지
- BYOK(본인 API 키) 지원

### 🎓 Q&A 챗봇

AI·SW마에스트로 공식 사이트(swmaestro.ai)의 공개 정보를 기반으로 자주 묻는 질문에 답변하는 RAG 챗봇입니다.

- 웹 크롤링 → 청크 → 임베딩 → 벡터 검색 → LLM 답변
- 캐시(동일 질문 + 유사 질문) + 멀티턴 대화 + 사용자 피드백 수집
- 8-모델 폴백 체인

### 🔒 통합 관리자

비밀번호로 보호된 대시보드. 두 기능의 로그/제출 내역/통계/다운로드를 한 곳에서 관리합니다.

---

## 평가 기준 출처 (Credit)

포트폴리오 코치의 **10가지 평가 기준**은 카카오톡 오픈채팅방 **"소프트웨어 마에스트로 준비방"** 에서 **엄지척 재이지(SW마에스트로 15기)** 님이 공유해주신 포트폴리오 꿀팁을 기반으로 만들어졌습니다.

원작자의 통찰을 자동화된 도구로 옮긴 것이며, 모든 평가 기준의 본질은 원본에 있습니다. 멘티들이 더 많은 도움을 받을 수 있도록 공유해주신 점에 감사드립니다.

---

## 기술 스택

- **언어**: Python 3.11+
- **웹 UI**: Streamlit (multipage `st.navigation`)
- **LLM**: Google Gemini 2.5 Flash (멀티모달, 8-모델 폴백)
- **DB**: Supabase Postgres (로그/카운터/메타) + Storage (포트폴리오 zip 보관)
- **HTTP**: requests (Gemini REST API 직접 호출, SDK 미사용)
- **이미지 처리**: Pillow (Notion zip 내 이미지 리사이즈/base64 인코딩)
- **테스트**: pytest + pytest-mock (58개 단위 테스트)

## 프로젝트 구조

```
.
├── app.py                                # Streamlit navigation hub (entry)
├── page_views/                           # 페이지별 본문
│   ├── portfolio_coach.py
│   ├── qa_chatbot.py
│   └── admin.py
├── portfolio/                            # 포트폴리오 코치 모듈
│   ├── parser.py                         # Notion zip → ParsedPortfolio
│   ├── prompts.py                        # 시스템 프롬프트 + JSON 스키마
│   ├── llm.py                            # Gemini 멀티모달 호출 + 8-모델 폴백
│   ├── evaluator.py                      # Call 1: 10항목 평가
│   ├── question_gen.py                   # Call 2: 카테고리별 면접 질문
│   ├── compose_md.py                     # 결과 → 마크다운 페이지
│   ├── storage.py                        # Supabase Storage REST 래퍼
│   ├── ratelimit.py                      # IP/일일 RPD 카운터
│   ├── ui.py                             # Streamlit 사용자 페이지 본문
│   └── admin.py                          # 관리자 본문
├── rag/                                  # Q&A 챗봇 RAG 모듈
│   ├── chain.py                          # LLM 호출 + 폴백
│   ├── embedder.py                       # Gemini 임베딩
│   ├── retriever.py                      # 벡터 검색
│   ├── cache.py                          # 응답 캐시
│   ├── feedback.py                       # 피드백 수집
│   └── db.py                             # Supabase REST 래퍼 (범용)
├── scraper/                              # swmaestro.ai 크롤러
├── scripts/                              # 스크래핑/인덱싱 실행
├── data/                                 # 크롤링 원본 + 청크
├── migrations/                           # Supabase SQL 마이그레이션
├── tests/portfolio/                      # 포트폴리오 모듈 단위 테스트
└── docs/
    ├── specs/                            # 설계 문서
    └── plans/                            # 구현 계획
```

## 시작하기

### 1. 의존성 설치

```bash
pip install -r requirements.txt
# 개발(테스트 포함)
pip install -r requirements-dev.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 다음 값 입력:

| 키 | 필수 | 설명 |
|---|---|---|
| `GOOGLE_API_KEY` | ✅ | Q&A 챗봇용 Gemini 키 |
| `GOOGLE_API_KEY_PORTFOLIO` | 선택 | 포트폴리오 코치용 별도 Gemini 키 (할당량 격리). 미설정 시 `GOOGLE_API_KEY` 사용 |
| `SUPABASE_URL` | ✅ | Supabase 프로젝트 URL |
| `SUPABASE_KEY` | ✅ | Supabase anon/service 키 |
| `ADMIN_PASSWORD` | 선택 | 관리자 페이지 비밀번호 (기본값 `admin1234`) |
| `IP_HASH_SALT` | 선택 | IP 해시 salt (기본값 하드코딩) |
| `LOG_WEBHOOK_URL` | 선택 | 로그 백업용 Google Apps Script webhook |

### 3. Supabase 세팅

#### Q&A 챗봇용 (필요시)

```bash
python scripts/scrape.py
python scripts/index.py
```

#### 포트폴리오 코치용

Supabase 콘솔의 SQL Editor에서 다음 파일 실행:

```
migrations/2026-04-09-portfolio.sql
```

생성되는 것:
- `portfolio_submissions` 테이블 (제출 이력)
- `portfolio_ratelimit` 테이블 (IP 카운터)
- `portfolio_daily_count` 테이블 (전역 RPD 카운터)
- `portfolio-uploads` Storage 버킷 (private)

### 4. 실행

```bash
streamlit run app.py
```

브라우저에서 http://localhost:8501 열림. 사이드바에서 페이지 전환.

### 5. 테스트

```bash
pytest tests/portfolio/ -v
```

58개 테스트 통과해야 합니다.

## Streamlit Cloud 배포

1. GitHub에 push (`main` 브랜치 자동 추적)
2. [share.streamlit.io](https://share.streamlit.io) → 앱 선택 → Settings → Secrets에 위 환경변수 등록 (TOML 형식)
3. 자동 재배포 후 동작 확인

## 라이선스

이 도구의 평가 기준은 원작자(엄지척 재이지, SW마에스트로 15기)의 통찰에 기반합니다. 코드 자체는 학습/참고 목적으로 자유롭게 이용 가능합니다. 단, 평가 기준 원본을 인용할 때는 원작자를 명시해주세요.
