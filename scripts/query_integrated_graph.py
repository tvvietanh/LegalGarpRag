"""Print actual offline concept->definition->document traversals; no server/API."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from legal_graph.integration import traversal_examples

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--graph", type=Path, default=Path("outputs/integrated_graph"))
parser.add_argument("--concept", default="fixed_term_labor_contract")
args = parser.parse_args()
nodes = [json.loads(line) for line in (args.graph / "nodes.jsonl").read_text(encoding="utf-8").splitlines()]
edges = [json.loads(line) for line in (args.graph / "edges.jsonl").read_text(encoding="utf-8").splitlines()]
result = traversal_examples(nodes, edges)
selected = [row for row in result["graph_traversals"] if row["node_ids"][0] == "ontology:concept:" + args.concept]
sys.stdout.reconfigure(encoding="utf-8")
print(json.dumps({"traversals": selected, "case_graph_links": result["case_graph_links"]}, ensure_ascii=False, sort_keys=True, indent=2))
