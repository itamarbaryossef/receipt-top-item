"""Runs the find-top-item task with DeepSeek V4 Flash (through OpenRouter, as RUSH Lab does) on every
inputs/*.json, one run folder each under runs/: result.json (the agent's answer), reference.json (the
answer key), verdict.json (the verifier's verdict), messages.json (the conversation) and run.log.
A run folder that already exists is kept, not rerun. Then writes, in runs/: summary.md, and every
run's input, verdict and log gathered in all_inputs.json, all_verdicts.json and all_run_logs.log.
From the plugin root:

    export OPENROUTER_API_KEY=...   # never commit it
    uv run --project tests/evals python tests/evals/run.py
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]
RUNS = HERE / "runs"

if not os.environ.get("OPENROUTER_API_KEY"):
    sys.exit("set OPENROUTER_API_KEY first")

# On a macOS folder synced by iCloud, the plugin's editable-install .pth file can be flagged hidden,
# and Python 3.13+ skips hidden .pth files, so the plugin does not import. A .pth written anew is visible.
for pth in PLUGIN.glob(".venv/lib/python3.*/site-packages/__editable__*.pth"):
    if getattr(pth.stat(), "st_flags", 0) & getattr(stat, "UF_HIDDEN", 0):
        content = pth.read_bytes()
        pth.unlink()
        pth.write_bytes(content)

RUNS.mkdir(exist_ok=True)
inputs = sorted((HERE / "inputs").glob("*.json"), key=lambda path: int(path.stem))
for input_file in inputs:
    home = RUNS / input_file.stem
    if home.exists():
        print(f"skip {input_file.stem} (already run)")
        continue
    print(f"run  {input_file.stem}: {input_file.read_text().strip()}", flush=True)
    command = ["nanoagent", "plugin", "agent", f"config={HERE / 'agent.yaml'}", f"home={home}", "--"]
    command += [f"plugin={PLUGIN}", f"arguments={input_file}"]
    with (RUNS / f"{input_file.stem}.out").open("w") as out:
        # The run exits 1 when the verdict is invalid; that is a result, not a failure of this script.
        code = subprocess.run(command, check=False, cwd=HERE, stdout=out, stderr=subprocess.STDOUT).returncode
    print(f"     exit {code} -> runs/{input_file.stem}")

rows, verdicts, logs, passed = [], {}, [], 0
for input_file in inputs:
    run = RUNS / input_file.stem
    if (run / "run.log").is_file():
        logs.append(f"##### seed {input_file.stem}\n{(run / 'run.log').read_text().rstrip()}\n")
    if not (run / "verdict.json").is_file():
        rows.append(f"| {input_file.stem} | (no verdict: see runs/{input_file.stem}.out) | | | |")
        continue
    verdict = json.loads((run / "verdict.json").read_text())
    verdicts[input_file.stem] = verdict
    answer = json.loads((run / "result.json").read_text())["output"]["item"]
    expected = json.loads((run / "reference.json").read_text())["response"]["item"]
    passed += verdict["valid"]
    mark = "valid" if verdict["valid"] else "invalid"
    rows.append(f"| {input_file.stem} | {answer} | {expected} | {mark}, {verdict['score']} | {verdict['message']} |")
lines = [
    "# receipt-top-item: DeepSeek V4 Flash runs",
    "",
    "| Seed | Agent's answer | Expected | Verdict | Verifier's message |",
    "|---|---|---|---|---|",
    *rows,
    "",
    f"**Valid: {passed} / {len(inputs)}**",
]
(RUNS / "summary.md").write_text("\n".join(lines) + "\n")
all_inputs = {input_file.stem: json.loads(input_file.read_text()) for input_file in inputs}
(RUNS / "all_inputs.json").write_text(json.dumps(all_inputs, indent=2) + "\n")
(RUNS / "all_verdicts.json").write_text(json.dumps(verdicts, indent=2, ensure_ascii=False) + "\n")
(RUNS / "all_run_logs.log").write_text("\n".join(logs))
print("\n".join(lines))
