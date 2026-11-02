from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

from contract import AnswerKeyOutput, ReceiptInput
from plugin.receipt import (
    CHAR,
    HEIGHT,
    JITTER_Y,
    LEFT,
    NAMES,
    QUANTITY_X,
    ROW,
    SCAN_FILE,
    TOP,
    WIDTH,
    answer_key,
    scan_receipt,
)
from verifier.key import key_problem

SEEDS = range(300)


def _lines(tokens):
    """The printed lines, rebuilt from the boxes alone: words close in y share a line, read left to right."""
    lines = []
    for token in sorted(tokens, key=lambda token: token.box[1]):
        if lines and token.box[1] - lines[-1][0].box[1] <= ROW // 2:
            lines[-1].append(token)
        else:
            lines.append([token])
    return [" ".join(token.text for token in sorted(line, key=lambda token: token.box[0])) for line in lines]


def test_the_same_seed_scans_the_same_receipt(tmp_path: Path) -> None:
    first = plain_output(scan_receipt(ReceiptInput(seed=7), tmp_path))
    assert plain_output(scan_receipt(ReceiptInput(seed=7), tmp_path)) == first
    assert plain_output(scan_receipt(ReceiptInput(seed=8), tmp_path)) != first
    assert (tmp_path / SCAN_FILE).is_file()


def test_every_name_ends_before_the_quantity_column() -> None:
    assert all(LEFT + len(name) * CHAR < QUANTITY_X for name in NAMES)


def test_words_stay_on_the_page_and_lines_never_touch(tmp_path: Path) -> None:
    for seed in SEEDS:
        scanned = scan_receipt(ReceiptInput(seed=seed), tmp_path)
        assert scanned.width == WIDTH
        rows = {}
        for token in scanned.tokens:
            x0, y0, x1, y1 = token.box
            assert 0 <= x0 < x1 <= scanned.width and 0 <= y0 < y1 <= scanned.height, (seed, token)
            assert y1 - y0 == HEIGHT
            row = round((y0 - TOP) / ROW)
            assert abs(y0 - (TOP + row * ROW)) <= JITTER_Y
            rows.setdefault(row, []).append(token.box)
        ordered = sorted(rows)
        for upper, lower in pairwise(ordered):
            assert max(box[3] for box in rows[upper]) < min(box[1] for box in rows[lower]), seed


def test_the_lines_rebuilt_from_the_boxes_read_the_receipt(tmp_path: Path) -> None:
    for seed in SEEDS:
        given = ReceiptInput(seed=seed)
        key = answer_key(given, tmp_path)
        lines = _lines(scan_receipt(given, tmp_path).tokens)
        items = [f"{item.name} {item.quantity} x {item.unit_price} {item.line_total}" for item in key.items]
        assert lines[0] == key.store
        assert lines[1 : 1 + len(items)] == items
        assert lines[-3:] == [f"SUBTOTAL {key.subtotal}", f"TAX 8.25% {key.tax}", f"TOTAL {key.total}"]
        assert len(lines) == len(items) + 4


def test_every_receipt_has_one_answer_and_keeps_its_traps(tmp_path: Path) -> None:
    for seed in SEEDS:
        key = build_output(plain_output(answer_key(ReceiptInput(seed=seed), tmp_path)), AnswerKeyOutput)
        assert key_problem(key) is None, seed


@pytest.mark.parametrize("seed", [-1, 1_000_000])
def test_refuses_a_seed_out_of_range(seed: int, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="seed"):
        scan_receipt(ReceiptInput(seed=seed), tmp_path)
