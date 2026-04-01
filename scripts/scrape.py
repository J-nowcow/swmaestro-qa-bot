"""swmaestro.ai 크롤링 실행 스크립트"""
import json
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.crawler import crawl_all
from scraper.parser import parse_all


def main():
    print("=" * 50)
    print("SW마에스트로 사이트 크롤링 시작")
    print("=" * 50)

    # 1) 크롤링
    results = crawl_all("data/raw")

    # 크롤링 결과 저장 (파싱에서 사용)
    results_file = Path("data/raw/crawl_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n크롤링 결과 메타데이터 → {results_file}")

    # 2) 파싱
    print("\n" + "=" * 50)
    print("HTML → 마크다운 청크 변환")
    print("=" * 50)
    chunks = parse_all(results, "data/raw", "data/processed")

    print(f"\n완료! data/processed/chunks.json 에서 결과 확인 가능")


if __name__ == "__main__":
    main()
