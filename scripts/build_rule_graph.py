"""CLI for the offline M1 Rule Graph; Python standard library only."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from legal_graph.rule_graph import main


if __name__ == "__main__":
    raise SystemExit(main())
