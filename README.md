# SW마에스트로 Q&A 챗봇

AI·SW마에스트로 공식 사이트(swmaestro.ai)의 공개 정보를 기반으로 자주 묻는 질문에 답변하는 RAG 챗봇입니다.

## 기술 스택

- **LLM**: Google Gemini 2.0 Flash (무료)
- **Embedding**: Gemini Embedding (gemini-embedding-001)
- **Vector DB**: ChromaDB
- **Web UI**: Streamlit
- **RAG**: LangChain

## 시작하기

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. API 키 설정

```bash
cp .env.example .env
# .env 파일에 Google AI Studio에서 발급받은 API 키 입력
```

### 3. 데이터 수집 (스크래핑)

```bash
python scripts/scrape.py
```

### 4. 인덱스 생성 (임베딩)

```bash
python scripts/index.py
```

### 5. 챗봇 실행

```bash
streamlit run app.py
```

## 프로젝트 구조

```
├── app.py                 # Streamlit 메인 앱
├── scraper/
│   ├── crawler.py         # swmaestro.ai 크롤러
│   └── parser.py          # HTML → 마크다운 변환
├── rag/
│   ├── embedder.py        # Gemini 임베딩 + ChromaDB
│   ├── retriever.py       # 유사도 검색
│   └── chain.py           # RAG 체인 (답변 생성)
├── scripts/
│   ├── scrape.py          # 스크래핑 실행
│   └── index.py           # 인덱싱 실행
└── data/
    ├── raw/               # 크롤링 원본
    └── processed/         # 변환된 청크
```

## Streamlit Cloud 배포

1. GitHub에 push
2. [share.streamlit.io](https://share.streamlit.io)에서 배포
3. Secrets에 `GOOGLE_API_KEY` 추가
