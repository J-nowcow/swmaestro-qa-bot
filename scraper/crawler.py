"""swmaestro.ai 웹 크롤러"""
import time
import requests
from pathlib import Path

BASE_URL = "https://swmaestro.ai"

# 스크래핑 대상 페이지 정의
PAGES = [
    # FAQ 게시판
    {
        "url": "/sw/bbs/B0000004/list.do?menuNo=200021",
        "title": "연수생 모집 FAQ",
        "type": "faq",
    },
    {
        "url": "/sw/bbs/B0000021/list.do?menuNo=200090",
        "title": "코딩테스트 FAQ",
        "type": "faq",
    },
    # 정적 콘텐츠 페이지
    {
        "url": "/sw/main/contents.do?menuNo=200002",
        "title": "AI·SW마에스트로 소개",
        "type": "content",
    },
    {
        "url": "/sw/main/contents.do?menuNo=200004",
        "title": "주요성과",
        "type": "content",
    },
    {
        "url": "/sw/main/contents.do?menuNo=200089",
        "title": "코딩테스트 학습가이드",
        "type": "content",
    },
    {
        "url": "/sw/main/contents.do?menuNo=200034",
        "title": "멘토 모집공고",
        "type": "content",
    },
    # 모집공고
    {
        "url": "/sw/main/notifyMentee.do?menuNo=200091",
        "title": "제17기 연수생 모집공고",
        "type": "content",
    },
    # 뉴스 게시판 (목록)
    {
        "url": "/sw/bbs/B0000002/list.do?menuNo=200019",
        "title": "소마 소식",
        "type": "board_list",
        "board_code": "B0000002",
        "menu_no": "200019",
        "max_pages": 3,
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def fetch_page(url: str) -> str | None:
    """단일 페이지 HTML을 가져옴"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    full_url = url if url.startswith("http") else f"{BASE_URL}{url}"
    try:
        resp = requests.get(full_url, headers=HEADERS, timeout=15, verify=False)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return resp.text
    except requests.RequestException as e:
        print(f"[ERROR] {full_url}: {e}")
        return None


def fetch_board_detail_urls(board_code: str, menu_no: str, max_pages: int = 3) -> list[dict]:
    """게시판 목록에서 개별 글 URL 추출"""
    from bs4 import BeautifulSoup

    detail_urls = []
    for page in range(1, max_pages + 1):
        url = f"/sw/bbs/{board_code}/list.do?menuNo={menu_no}&pageIndex={page}"
        html = fetch_page(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        # href에 view.do가 포함된 모든 링크 추출
        for link in soup.select("a[href*='view.do']"):
            href = link.get("href", "")
            title = link.get_text(strip=True)
            if title and len(title) > 2:
                detail_url = href if href.startswith("/") else f"/sw/bbs/{board_code}/{href}"
                detail_urls.append({"url": detail_url, "title": title})

        time.sleep(1)  # rate limiting

    # 중복 제거
    seen = set()
    unique = []
    for item in detail_urls:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)
    return unique


def crawl_all(output_dir: str = "data/raw") -> list[dict]:
    """모든 대상 페이지를 크롤링하여 저장"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []

    for i, page in enumerate(PAGES):
        print(f"[{i+1}/{len(PAGES)}] 크롤링: {page['title']}")

        if page["type"] == "board_list":
            # 게시판: 목록에서 개별 글 URL 추출 후 각각 크롤링
            detail_urls = fetch_board_detail_urls(
                page["board_code"], page["menu_no"], page.get("max_pages", 3)
            )
            print(f"  → {len(detail_urls)}개 글 발견")

            for j, detail in enumerate(detail_urls[:30]):  # 최대 30건
                html = fetch_page(detail["url"])
                if html:
                    source_url = f"{BASE_URL}{detail['url']}"
                    filename = f"{page['board_code']}_{j:03d}.html"
                    (output_path / filename).write_text(html, encoding="utf-8")
                    results.append({
                        "file": filename,
                        "title": detail["title"],
                        "source_url": source_url,
                        "type": "board_detail",
                        "page_title": page["title"],
                    })
                time.sleep(1)
        else:
            # FAQ 또는 정적 콘텐츠
            html = fetch_page(page["url"])
            if html:
                source_url = f"{BASE_URL}{page['url']}"
                filename = f"page_{i:03d}.html"
                (output_path / filename).write_text(html, encoding="utf-8")
                results.append({
                    "file": filename,
                    "title": page["title"],
                    "source_url": source_url,
                    "type": page["type"],
                    "page_title": page["title"],
                })

        time.sleep(1)  # rate limiting

    print(f"\n총 {len(results)}개 페이지 크롤링 완료 → {output_dir}/")
    return results
