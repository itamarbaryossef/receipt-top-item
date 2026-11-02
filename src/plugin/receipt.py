from __future__ import annotations

import json
import random
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from slimconfig import plain_output

from contract import AnswerKeyOutput, Item, ReceiptInput, ScanOutput, Token

SEEDS = 1_000_000  # a seed is in range(SEEDS)
QUESTION = "Which item has the highest line total?"
# Names share words ("Oat Milk", "Whole Milk", "Milk Chocolate Bar"), so a single word rarely names
# an item, and a name must be rebuilt from its words.
NAMES = (
    "Oat Milk", "Whole Milk", "Almond Milk", "Greek Yogurt", "Vanilla Yogurt", "Sourdough Bread",
    "Wheat Bread", "Cheddar Cheese", "Swiss Cheese", "Ground Coffee", "Coffee Beans", "Orange Juice",
    "Apple Juice", "Large Eggs", "Brown Rice", "Basmati Rice", "Penne Pasta", "Salted Butter",
    "Peanut Butter", "Green Tea", "Black Tea", "Dark Chocolate Bar", "Milk Chocolate Bar", "Bagels",
    "Bananas", "Avocados", "Paper Towels", "Dish Soap", "Olive Oil", "Tomato Sauce",
)  # fmt: skip
STORE_WORDS = (
    ("Green", "Corner", "Daily", "Fresh", "Sunny", "Harbor", "Maple", "Union"),
    ("Grocer", "Market", "Pantry", "Foods", "Mart", "Basket"),
)
ITEMS = (4, 8)  # fewest and most item lines
QUANTITIES = (1, 5)
CENTS = (49, 1999)  # cheapest and dearest unit price, in cents
TAX_RATE = Decimal("0.0825")
ATTEMPTS = 1000
SCAN_FILE = "receipt.json"
# The page, in pixels: words are CHAR wide per character and HEIGHT tall, one printed line per ROW.
WIDTH, LEFT, RIGHT, TOP = 400, 20, 380, 20
QUANTITY_X = 200  # where the "2 x 3.49" column starts; every name ends before it
CHAR, HEIGHT, ROW = 8, 14, 24
# How far OCR moves each word off its line, in pixels: never enough to reach a neighbouring line.
JITTER_X, JITTER_Y = 1, 3


@dataclass(frozen=True)
class Line:
    name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class Receipt:
    store: str
    date: str
    time: str
    lines: list[Line]
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    item: str


def make_receipt(given: ReceiptInput) -> tuple[Receipt, random.Random]:
    """The receipt ``given`` names and the generator, ready to lay it out: the same seed always makes the same."""
    if not 0 <= given.seed < SEEDS:
        raise ValueError(f"seed must be from 0 to {SEEDS - 1}, not {given.seed}")
    rng = random.Random(given.seed)
    store = " ".join(rng.choice(words) for words in STORE_WORDS)
    date = f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    time = f"{rng.randint(8, 21):02d}:{rng.randint(0, 59):02d}"
    for _ in range(ATTEMPTS):
        names = rng.sample(NAMES, rng.randint(*ITEMS))
        lines = []
        for name in names:
            quantity = rng.randint(*QUANTITIES)
            unit_price = Decimal(rng.randint(*CENTS)) / 100
            lines.append(Line(name, quantity, unit_price, quantity * unit_price))
        item = _top_item(lines)
        if item is not None:
            subtotal = sum((line.line_total for line in lines), Decimal("0.00"))
            tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return Receipt(store, date, time, lines, subtotal, tax, subtotal + tax, item), rng
    raise RuntimeError(f"no unambiguous receipt for seed {given.seed} in {ATTEMPTS} attempts")


def _top_item(lines):
    """The item with the highest line total, or None when these lines make the answer ambiguous or easy to guess."""
    by_total = sorted(lines, key=lambda line: line.line_total, reverse=True)
    by_price = sorted(lines, key=lambda line: line.unit_price, reverse=True)
    if by_total[0].line_total == by_total[1].line_total or by_price[0].unit_price == by_price[1].unit_price:
        return None
    # Ranking by unit price, or taking the first or last line, must give a wrong answer.
    if by_price[0] is by_total[0] or by_total[0] in (lines[0], lines[-1]):
        return None
    return by_total[0].name


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _rows(receipt: Receipt) -> list[list[tuple[str, int]]]:
    """Each printed line's words and where each starts, top to bottom; an empty list is a blank line."""

    def words(text, x):
        placed = []
        for word in text.split():
            placed.append((word, x))
            x += (len(word) + 1) * CHAR
        return placed

    def right(text):
        return (text, RIGHT - len(text) * CHAR)

    rows = [words(receipt.store, LEFT), [(receipt.date, LEFT), right(receipt.time)], []]
    for line in receipt.lines:
        price = [
            (str(line.quantity), QUANTITY_X),
            ("x", QUANTITY_X + 2 * CHAR),
            (_money(line.unit_price), QUANTITY_X + 4 * CHAR),
        ]
        rows.append(words(line.name, LEFT) + price + [right(_money(line.line_total))])
    rows += [
        [],
        [("SUBTOTAL", LEFT), right(_money(receipt.subtotal))],
        [("TAX", LEFT), (f"{TAX_RATE * 100:.2f}%", LEFT + 4 * CHAR), right(_money(receipt.tax))],
        [("TOTAL", LEFT), right(_money(receipt.total))],
        [],
        words("THANK YOU", LEFT),
    ]
    return rows


def scan(receipt: Receipt, rng: random.Random) -> tuple[int, list[Token]]:
    """The page's height and the receipt's words as OCR returns them: jittered boxes, in shuffled order."""
    rows = _rows(receipt)
    tokens = []
    for index, row in enumerate(rows):
        y = TOP + index * ROW
        for text, x in row:
            x0, y0 = x + rng.randint(-JITTER_X, JITTER_X), y + rng.randint(-JITTER_Y, JITTER_Y)
            tokens.append(Token(text=text, box=[x0, y0, x0 + len(text) * CHAR, y0 + HEIGHT]))
    rng.shuffle(tokens)
    return TOP + len(rows) * ROW + TOP, tokens


def scan_receipt(given: ReceiptInput, workspace: Path) -> ScanOutput:
    receipt, rng = make_receipt(given)
    height, tokens = scan(receipt, rng)
    output = ScanOutput(path=SCAN_FILE, width=WIDTH, height=height, tokens=tokens, question=QUESTION)
    saved = {key: value for key, value in plain_output(output).items() if key != "path"}
    (workspace / SCAN_FILE).write_text(json.dumps(saved, indent=1) + "\n", encoding="utf-8")
    return output


def answer_key(given: ReceiptInput, workspace: Path) -> AnswerKeyOutput:
    """The pinned answer for the receipt ``given`` names; NanoAgent runs it before the agent, out of its sight."""
    receipt, _ = make_receipt(given)
    items = [Item(line.name, line.quantity, _money(line.unit_price), _money(line.line_total)) for line in receipt.lines]
    return AnswerKeyOutput(
        store=receipt.store,
        items=items,
        subtotal=_money(receipt.subtotal),
        tax=_money(receipt.tax),
        total=_money(receipt.total),
        item=receipt.item,
    )
