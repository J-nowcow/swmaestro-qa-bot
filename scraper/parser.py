"""HTML을 마크다운 청크로 변환하고 메타데이터를 부여"""
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

# 제거할 네비게이션/UI 문구
NOISE_PATTERNS = [
    r"메뉴 건너띄기",
    r"상단메뉴 바로가기",
    r"본문 바로가기",
    r"로딩 중입니다\.\.\.",
    r"HOME\s*\n",
    r"사업소개\s*\n",
    r"모집안내\s*\n",
    r"도전과 성장\s*\n",
    r"알림마당\s*\n",
    r"AI·SW마에스트로\s*\n(?=연혁)",
    r"제\d+기 연수생 모집 공고\s*\n(?=연수생 모집 FAQ|코딩테스트)",
    r"연수생 모집 FAQ\s*\n(?=코딩테스트|2\d{3}년 멘토)",
    r"코딩테스트 사전 학습가이드\s*\n(?=2\d{3}년 멘토|코딩테스트 FAQ)",
    r"2\d{3}년 멘토 모집공고\s*\n(?=코딩테스트 FAQ)",
    r"코딩테스트 FAQ\s*\n(?=Total|제\d+기)",
    r"연혁\s*\n(?=기수별)",
    r"기수별 활동 현황\s*\n(?=주요성과)",
    r"주요성과\s*\n(?=연도별)",
    r"Total\s*:\s*\d+\s*\n",
    r"\d+\s*/\s*\d+\s*Page",
    r"검색어\s*분류 선택\s*\n",
    r"제목\s*\n내용\s*\n검색",
    r"리스트 화면\s*\n제목\s*\n작성자",
    r"(이전글|다음글|목록|첨부파일)\s*\n?",
    r"홈\s*>\s*.+?\n",
]


def parse_faq_page(html: str, source_url: str, page_title: str) -> list[dict]:
    """FAQ 페이지에서 Q&A 쌍 추출 (tr.q / tr.a 패턴)"""
    soup = BeautifulSoup(html, "html.parser")
    chunks = []

    # tr.q / tr.a 패턴 직접 탐색 (전체 문서에서)
    q_rows = soup.select("tr.q")
    for q_row in q_rows:
        question = q_row.get_text(strip=True)
        # 끝에 붙는 "사무국" 등 작성자 제거
        question = re.sub(r"사무국$", "", question).strip()

        a_row = q_row.find_next_sibling("tr", class_="a")
        if a_row:
            answer = a_row.get_text(separator="\n", strip=True)
            if question and answer:
                chunks.append({
                    "content": f"**Q: {question}**\n\n{answer}",
                    "metadata": {
                        "source_url": source_url,
                        "page_title": page_title,
                        "section": question[:80],
                        "type": "faq",
                    },
                })

    return chunks if chunks else _parse_as_content(html, source_url, page_title)


def parse_content_page(html: str, source_url: str, page_title: str) -> list[dict]:
    """정적 콘텐츠 페이지를 마크다운 청크로 변환"""
    return _parse_as_content(html, source_url, page_title)


def parse_board_detail(html: str, source_url: str, page_title: str, article_title: str = "") -> list[dict]:
    """게시판 상세 글을 마크다운 청크로 변환"""
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one(".view-title, .bbs-view h3, .board-view .title, .tit")
    if title_el:
        article_title = title_el.get_text(strip=True) or article_title

    content_el = soup.select_one(
        ".view-content, .bbs-view .cont, .board-view .cont, "
        ".view_cont, #articleBody, .article-body, .cont"
    )
    if not content_el:
        content_el = soup.select_one("#contents, .contents, main")

    if not content_el:
        return []

    text = _clean_text(content_el.get_text(separator="\n", strip=True))
    if len(text) < 20:
        return []

    return _chunk_text(
        text=f"# {article_title}\n\n{text}" if article_title else text,
        source_url=source_url,
        page_title=page_title,
        section=article_title,
    )


def _parse_as_content(html: str, source_url: str, page_title: str) -> list[dict]:
    """일반 콘텐츠로 파싱"""
    soup = BeautifulSoup(html, "html.parser")

    # 불필요한 태그 제거
    for tag in soup.select("script, style, nav, header, footer, .gnb, .lnb, .footer, .skip-navi"):
        tag.decompose()

    content_el = soup.select_one(
        "#contents, .contents, .sub-contents, .page-content, main, article"
    )
    if not content_el:
        content_el = soup.select_one("body")

    if not content_el:
        return []

    text = _clean_text(content_el.get_text(separator="\n", strip=True))
    if len(text) < 20:
        return []

    return _chunk_text(text, source_url, page_title, section=page_title)


def _clean_text(text: str) -> str:
    """네비게이션 노이즈 및 불필요한 UI 문구 제거"""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, "", text)

    # 연속 공백/줄바꿈 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _chunk_text(
    text: str,
    source_url: str,
    page_title: str,
    section: str = "",
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    """텍스트를 적절한 크기로 청킹"""
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": {
                    "source_url": source_url,
                    "page_title": page_title,
                    "section": section[:80] if section else page_title,
                    "type": "content",
                },
            })
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para

    if current_chunk.strip():
        chunks.append({
            "content": current_chunk.strip(),
            "metadata": {
                "source_url": source_url,
                "page_title": page_title,
                "section": section[:80] if section else page_title,
                "type": "content",
            },
        })

    return chunks


def parse_all(crawl_results: list[dict], raw_dir: str = "data/raw", output_dir: str = "data/processed") -> list[dict]:
    """크롤링 결과 전체를 파싱하여 청크로 변환"""
    raw_path = Path(raw_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_chunks = []

    for result in crawl_results:
        filepath = raw_path / result["file"]
        if not filepath.exists():
            continue

        html = filepath.read_text(encoding="utf-8")
        page_type = result["type"]

        if page_type == "faq":
            chunks = parse_faq_page(html, result["source_url"], result["page_title"])
        elif page_type == "board_detail":
            chunks = parse_board_detail(
                html, result["source_url"], result["page_title"], result.get("title", "")
            )
        else:
            chunks = parse_content_page(html, result["source_url"], result["page_title"])

        print(f"  {result['page_title']}: {len(chunks)}개 청크")
        all_chunks.extend(chunks)

    output_file = output_path / "chunks.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"총 {len(all_chunks)}개 청크 생성 → {output_file}")
    return all_chunks
