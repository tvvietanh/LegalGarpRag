"""Freeze real full-suite results and all219 Data hashes as offline QA inputs."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from legal_graph.rule_graph import canonical, digest_bytes

snapshot = json.loads((ROOT / "outputs/milestone_0/inventory.json").read_bytes())
expected = snapshot["files"]
actual = []
for path in sorted((ROOT / "Data").rglob("*")):
    if path.is_file():
        with path.open("rb") as stream:
            sha = hashlib.file_digest(stream, "sha256").hexdigest()
        actual.append({"path": path.relative_to(ROOT / "Data").as_posix(), "bytes": path.stat().st_size, "sha256": sha})
if sorted(actual, key=lambda r: r["path"]) != expected:
    raise SystemExit("Final QA FAIL: Data changed from M0 snapshot")
process = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
log = (process.stdout + process.stderr).encode("utf-8")
folder = ROOT / "docs/milestone_5";folder.mkdir(parents=True, exist_ok=True)
(folder / "TEST_LOG.txt").write_bytes(log)
if process.returncode != 0:
    raise SystemExit("Final unit suite FAIL;see docs/milestone_5/TEST_LOG.txt")
match = re.search(rb"Ran (\d+) tests", log)
if not match:
    raise SystemExit("Unit test count not found")
code = {path.relative_to(ROOT).as_posix(): digest_bytes(path.read_bytes()) for base in ("src", "scripts", "tests") for path in sorted((ROOT / base).rglob("*.py"))}
proof = {"schema_version": "final-qa-v1", "tests_passed": int(match.group(1)), "test_failures": 0, "test_errors": 0,
         "test_command": "python -B -m unittest discover -s tests -v", "test_log_sha256": digest_bytes(log),
         "all_219_data_hashes_match": True, "data_file_count": len(actual), "tracked_data_files": 218,
         "dataset_digest": snapshot["dataset_digest"], "m0_inventory_sha256": digest_bytes((ROOT / "outputs/milestone_0/inventory.json").read_bytes()),
         "validated_source_sha256": code}
audit = ROOT / "audit";audit.mkdir(exist_ok=True)
(audit / "final_qa_v1.json").write_bytes((canonical(proof) + "\n").encode("utf-8"))
print(f"Final QA PASS:tests={proof['tests_passed']};219Data hashes unchanged;QAproof frozen.")
