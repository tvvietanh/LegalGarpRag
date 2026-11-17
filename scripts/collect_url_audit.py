"""Optional one-pass bounded network audit. Offline final exporter never calls this."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
if (ROOT / ".codex_tmp/url_audit_deps").is_dir():
    sys.path.insert(0, str(ROOT / ".codex_tmp/url_audit_deps"))
from legal_graph.url_audit import collect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--graph", type=Path, default=Path("outputs/integrated_graph"))
parser.add_argument("--data", type=Path, default=Path("Data"))
parser.add_argument("--output", type=Path, default=Path("audit/url_observations_v1.jsonl"))
args = parser.parse_args()
sys.stdout.reconfigure(encoding="utf-8")
nodes = [json.loads(line) for line in (args.graph / "nodes.jsonl").read_text(encoding="utf-8").splitlines()]
if args.data.resolve() == args.output.resolve() or args.data.resolve() in args.output.resolve().parents:
    raise SystemExit("Audit output must be outside immutable Data")
collect(nodes, args.data, args.output)
