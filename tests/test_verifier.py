from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import AnswerKeyOutput, AnswerOutput, ReceiptInput, ScanOutput
from plugin.receipt import answer_key, scan_receipt

TASK = "find-top-item"


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def _given(seed: int) -> ReceiptInput:
    return build_output({"seed": seed}, ReceiptInput)


def _key(seed: int, tmp_path: Path) -> dict:
    return plain_output(answer_key(_given(seed), tmp_path))


def _check(item: str, *, seed: int = 11, key: dict | None = None, tmp_path: Path) -> dict:
    key = _key(seed, tmp_path) if key is None else key
    output = build_output({"item": item}, AnswerOutput)
    return verifier.verify_task(TASK, _given(seed), output, build_output(key, AnswerKeyOutput), str(tmp_path))


def test_approves_the_tools_and_the_right_item(tmp_path: Path) -> None:
    for seed in range(20):
        given = _given(seed)
        scanned = build_output(plain_output(scan_receipt(given, tmp_path)), ScanOutput)
        key = _key(seed, tmp_path)
        assert verifier.verify_input("scan_receipt", given)["valid"] is True
        assert verifier.verify_output("scan_receipt", given, scanned, str(tmp_path))["valid"] is True
        assert verifier.verify_output("answer_key", given, build_output(key, AnswerKeyOutput), str(tmp_path))["valid"]
        verdict = _check(key["item"], seed=seed, tmp_path=tmp_path)
        assert verdict["valid"] is True and verdict["score"] == 1.0, verdict


def test_accepts_the_name_in_other_case_or_spacing(tmp_path: Path) -> None:
    item = _key(11, tmp_path)["item"]
    assert _check(f"  {item.upper().replace(' ', '   ')} ", tmp_path=tmp_path)["valid"] is True


def test_refuses_the_item_with_the_highest_unit_price(tmp_path: Path) -> None:
    key = _key(11, tmp_path)
    dearest = max(key["items"], key=lambda item: Decimal(item["unit_price"]))
    verdict = _check(dearest["name"], tmp_path=tmp_path)
    assert verdict["valid"] is False and verdict["score"] == 0.0
    assert verdict["details"]["given_has_highest_unit_price"] is True
    assert verdict["details"]["expected"] == key["item"]


def test_refuses_another_item_and_says_how_far_off_it_is(tmp_path: Path) -> None:
    key = _key(11, tmp_path)
    cheapest = min(key["items"], key=lambda item: Decimal(item["line_total"]))
    verdict = _check(cheapest["name"], tmp_path=tmp_path)
    assert verdict["valid"] is False and "does not have the highest line total" in verdict["message"]
    assert verdict["details"]["given_line_total"] == cheapest["line_total"]


def test_refuses_a_name_not_on_the_receipt(tmp_path: Path) -> None:
    key = _key(11, tmp_path)
    multi_word = next(item["name"] for item in key["items"] if " " in item["name"])
    for answer in [multi_word.split()[-1], "TOTAL", key["store"], f"{key['item']} 2"]:
        verdict = _check(answer, tmp_path=tmp_path)
        assert verdict["valid"] is False and "not an item on the receipt" in verdict["message"], answer
    verdict = _check("   ", tmp_path=tmp_path)
    assert verdict["valid"] is False and "names no item" in verdict["message"]


def test_refuses_a_key_that_does_not_follow_from_its_receipt(tmp_path: Path) -> None:
    key = _key(11, tmp_path)
    other = next(item["name"] for item in key["items"] if item["name"] != key["item"])
    line = dict(key["items"][0], line_total="0.01")
    for broken in [
        {**key, "item": other},  # the wrong answer
        {**key, "items": [line, *key["items"][1:]]},  # a line total that is not quantity × unit price
        {**key, "tax": "0.00"},  # totals that do not add up
        {**key, "items": key["items"][:3]},  # too few items
    ]:
        built = build_output(broken, AnswerKeyOutput)
        assert verifier.verify_output("answer_key", _given(11), built, str(tmp_path))["valid"] is False
        assert _check(key["item"], key=broken, tmp_path=tmp_path)["valid"] is False
    output = build_output({"item": key["item"]}, AnswerOutput)
    assert verifier.verify_task(TASK, _given(11), output, None, str(tmp_path))["valid"] is False


def test_refuses_a_scan_that_differs_from_the_saved_file_or_leaves_the_page(tmp_path: Path) -> None:
    given = _given(11)
    scanned = plain_output(scan_receipt(given, tmp_path))
    moved = {**scanned, "tokens": [{**scanned["tokens"][0], "box": [0, 0, 10, 10_000]}, *scanned["tokens"][1:]]}
    for broken in [moved, {**scanned, "question": "Which item is cheapest?"}]:
        verdict = verifier.verify_output("scan_receipt", given, build_output(broken, ScanOutput), str(tmp_path))
        assert verdict["valid"] is False and "not the one saved" in verdict["message"]
    (tmp_path / scanned["path"]).unlink()
    assert (
        verifier.verify_output("scan_receipt", given, build_output(scanned, ScanOutput), str(tmp_path))["valid"]
        is False
    )


def test_refuses_a_seed_out_of_range() -> None:
    verdict = verifier.verify_input("scan_receipt", _given(1_000_000))
    assert verdict["valid"] is False and "seed" in verdict["message"]
    assert verifier.verify_input("answer_key", _given(-1))["valid"] is False
