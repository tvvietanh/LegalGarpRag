"""Build the policy-constrained M3 Case Graph offline."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from legal_graph.fact_graph import main

if __name__ == "__main__":
    raise SystemExit(main())
