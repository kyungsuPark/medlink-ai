import argparse
import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from medlink.db import engine
from medlink.embeddings import get_embedder
from medlink.evaluation import evaluate
from medlink.ingest import LegacySnapshot, ingest
from medlink.models import Base
from medlink.sample import synthetic_export


def main():
    parser = argparse.ArgumentParser(description="MedLink synthetic HIS demo")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "init-db", help="Create extension and initial schema without resetting data"
    )
    generate = commands.add_parser("generate", help="Create the deterministic legacy JSON export")
    generate.add_argument("--output", type=Path, default=Path("data/legacy_his.json"))
    seed = commands.add_parser("seed", help="Validate, normalize and embed one immutable export")
    seed.add_argument("--input", type=Path, default=Path("data/legacy_his.json"))
    evaluation = commands.add_parser("evaluate", help="Run golden retrieval cases")
    evaluation.add_argument("--cases", type=Path, default=Path("data/evaluation.json"))
    evaluation.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    args = parser.parse_args()
    if args.command == "generate":
        payload = LegacySnapshot.model_validate(synthetic_export()).model_dump(mode="json")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Generated {len(payload['patients'])} synthetic patients: {args.output}")
    elif args.command == "init-db":
        with engine().begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            Base.metadata.create_all(connection)
        print("Schema ready")
    elif args.command == "seed":
        raw = LegacySnapshot.model_validate_json(args.input.read_text(encoding="utf-8"))
        with Session(engine()) as session:
            print(json.dumps(ingest(session, raw, get_embedder())))
    else:
        with Session(engine()) as session:
            report = evaluate(session, get_embedder(), args.cases)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
