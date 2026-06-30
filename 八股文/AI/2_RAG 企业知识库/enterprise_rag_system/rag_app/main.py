import argparse
from pathlib import Path

from .evaluator import evaluate_recall_at_k
from .generator import generate_answer
from .ingest import build_index
from .retriever import search_chunks
from .store import load_index


BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DIR = BASE_DIR / "data" / "docs"
INDEX_PATH = BASE_DIR / "data" / "index.json"
EVAL_PATH = BASE_DIR / "data" / "eval" / "eval_cases.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise RAG demo")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest", help="Build local index from data/docs")

    search_parser = subparsers.add_parser("search", help="Search relevant chunks")
    search_parser.add_argument("question")
    search_parser.add_argument("--top-k", type=int, default=5)

    ask_parser = subparsers.add_parser("ask", help="Generate answer with citations")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--top-k", type=int, default=5)

    subparsers.add_parser("eval", help="Evaluate recall@5")

    args = parser.parse_args()
    if args.command == "ingest":
        documents, chunks = build_index(DOCS_DIR, INDEX_PATH)
        print(f"indexed documents={documents}, chunks={chunks}, index={INDEX_PATH}")
        return

    if not INDEX_PATH.exists():
        raise SystemExit("index not found, run: python3 -m rag_app.main ingest")

    _, chunks = load_index(INDEX_PATH)

    if args.command == "search":
        for rank, result in enumerate(search_chunks(chunks, args.question, args.top_k), start=1):
            chunk = result.chunk
            print(
                f"{rank}. score={result.final_score:.3f} "
                f"vector={result.vector_score:.3f} keyword={result.keyword_score:.3f} "
                f"{chunk.document_title} / {chunk.section_path} / {chunk.id}"
            )
            print(chunk.content[:220].replace("\n", " "))
            print()
        return

    if args.command == "ask":
        results = search_chunks(chunks, args.question, args.top_k)
        print(generate_answer(args.question, results))
        return

    if args.command == "eval":
        metrics = evaluate_recall_at_k(chunks, EVAL_PATH, k=5)
        for key, value in metrics.items():
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
