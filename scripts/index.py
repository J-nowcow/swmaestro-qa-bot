"""ChromaDB 인덱스 생성 스크립트"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from rag.embedder import build_index


def main():
    print("=" * 50)
    print("ChromaDB 인덱스 생성 시작")
    print("=" * 50)

    chunks_file = "data/processed/chunks.json"
    if not Path(chunks_file).exists():
        print(f"오류: {chunks_file}이 없습니다.")
        print("먼저 python scripts/scrape.py를 실행하세요.")
        sys.exit(1)

    build_index(chunks_file)
    print("\n완료! 이제 streamlit run app.py 로 챗봇을 실행하세요.")


if __name__ == "__main__":
    main()
