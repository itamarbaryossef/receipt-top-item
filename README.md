# Receipt Top Item

A `nanoagent.plugin/v0001` plugin for document question answering by a text-only agent. Document
VQA pipelines often give a language model OCR output rather than an image: every word with its
bounding box. From a seed, `scan_receipt` makes a grocery receipt and returns exactly that, with the
words in shuffled order, and asks which item has the highest line total. The agent must rebuild the
receipt's lines from the boxes alone. A reference tool, `answer_key`, computes the answer from the
same seed before the agent starts, out of its sight, and the verifier compares the two with no model.

A receipt has a store name, 3 to 5 item lines and a subtotal, 8.25% tax and total.
An item line reads `Oat Milk  2 x 3.49  6.98`: a name of one to three words, the quantity, the unit
price and the line total, right-aligned. Item names share words ("Oat Milk", "Whole Milk", "Milk
Chocolate Bar"), so a name must be rebuilt from its words. Each word's box is moved up or down by
up to a pixel, as OCR does, but lines are 24 pixels apart, so words never reach a neighbouring line.
Receipts are kept this small so that DeepSeek V4 Flash's reasoning fits inside RUSH Lab's 2048-token
output limit: on larger, noisier receipts it sometimes spent the whole limit reasoning and never answered.

The generator rejects any receipt whose answer is ambiguous or easy to guess: the highest line total
is unique, the item with the highest unit price is a different item (so ranking by the wrong column,
or ignoring quantity, fails), and the answer is never the first or last item line.

## Tools

| Tool | Does | Code |
|---|---|---|
| `scan_receipt` | Scans the seeded receipt into OCR words with boxes, saves them as `receipt.json` in the workspace, and returns them with the question | `src/plugin/receipt.py` |
| `answer_key` | Computes the receipt's items and totals and the item with the highest line total; the `find-top-item` task's pinned reference | `src/plugin/receipt.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `find-top-item` | Finds the item with the highest line total on a receipt given as OCR words with boxes | `agent`, with `scan_receipt`; reference `answer_key` |

The task's input is `{"seed": <0 to 999999>}`, for example `{"seed": 42}`. Its output is
`{"item": "<name>"}`: the item's full name, as printed.

The verifier (`verifier/`) checks:

- `verify_input`: the seed is from 0 to 999999.
- `verify_output` of `scan_receipt`: the returned scan is the `receipt.json` saved in the workspace,
  the question is the task's, and every token is one word whose box lies on the page.
- `verify_output` of `answer_key`: the receipt adds up (each line total is quantity × unit price,
  the subtotal is their sum, and the tax and total follow), names are unique, amounts and quantities
  are in range, and the answer is the unique highest line total and keeps the traps above.
- `verify_task`: the same checks of the pinned key, then the agent's answer. An empty answer or a
  name that is not an item on the receipt (a single word of a name, "TOTAL", the store) is refused
  with its own message; otherwise the answer is right when it names the top item, ignoring case and
  spacing, and is scored 1 or 0. For a wrong item, `details` give its line total against the
  expected one and whether it is the item with the highest unit price.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs, never values (none)
├── src/plugin/      # the MCP server (__main__.py) and the receipt generator and tools (receipt.py)
├── tests/           # test_receipt.py (the generator), test_verifier.py (the verifier), evals/ (model runs)
├── ui/              # how the page draws the outputs: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package: scan.py, key.py and checks.py
```

`contract.py` is the one place a value's shape is declared. Its `Output` classes are the JSON
Schemas the server offers and the agent sees, and every input and output is built into its class
on the way in and out. A tool that fails raises; NanoAgent sees an MCP error. The plugin needs no
network, no API key and no data files: every receipt is computed from its seed with Python's
`random.Random`, and every amount with `decimal.Decimal`, so the same seed scans the same receipt
on every machine.

## Develop and run

Prerequisites: Git, Python 3.12 or later, and `uv`.

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

To see a scan and its answer key without an agent:

```bash
uv run python -c "
from pathlib import Path
from contract import ReceiptInput
from plugin.receipt import answer_key, scan_receipt
given = ReceiptInput(seed=42)
print(scan_receipt(given, Path('.')).tokens[:5])
print(answer_key(given, Path('.')))
"
```

This writes `receipt.json`, the full scan, to the current folder.

## Evaluating with a model

`tests/evals/` runs the `find-top-item` task end to end with the model and limits RUSH Lab uses
(DeepSeek V4 Flash through OpenRouter, `tests/evals/agent.yaml`) on the 15 seeds in
`tests/evals/inputs/`. It is its own uv project, which installs NanoAgent pinned to a commit of
github.com/RUSH-LAB/nanoagent, so it needs only Git, `uv` and an OpenRouter API key:

```bash
export OPENROUTER_API_KEY=...   # your own key; never commit it
uv run --project tests/evals python tests/evals/run.py
```

Each seed gets a folder `tests/evals/runs/<seed>/` holding `result.json` (the agent's answer),
`reference.json` (the answer key), `verdict.json` (the verifier's verdict), `messages.json` (the
conversation) and `run.log`. `tests/evals/runs/summary.md` tabulates them, and `all_inputs.json`,
`all_verdicts.json` and `all_run_logs.log` gather every run's input, verdict and log. A folder that
already exists is not rerun, so delete `tests/evals/runs/` to start over. The receipts, answer keys
and verdicts are deterministic, but the model's answers can differ from run to run.

Publishing checks every plugin rule: push the plugin to a public GitHub repository and submit its
URL in the RUSH Lab marketplace. In the plugin's chat, ask for example "Find the top item on receipt
42", and the result card shows the verifier's verdict.
