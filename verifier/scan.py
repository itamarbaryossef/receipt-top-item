"""scan_receipt: the scan it returns is the one it saved, and every word sits on the page."""

import json
from pathlib import Path

from .checks import result, verify_seed

QUESTION = "Which item has the highest line total?"


def verify_input(value):
    return verify_seed(value)


def verify_output(input_value, output_value, workspace):
    tokens = [{"text": token.text, "box": token.box} for token in output_value.tokens]
    returned = {
        "width": output_value.width,
        "height": output_value.height,
        "tokens": tokens,
        "question": output_value.question,
    }
    path = Path(workspace) / output_value.path
    if not path.is_file() or json.loads(path.read_text(encoding="utf-8")) != returned:
        return result(False, "the returned scan is not the one saved in the workspace", path=output_value.path)
    if output_value.question != QUESTION:
        return result(False, "the question is not the task's", question=output_value.question)
    if not tokens:
        return result(False, "the scan has no words")
    for token in output_value.tokens:
        if not token.text or token.text != "".join(token.text.split()):
            return result(False, "every token is one word", text=token.text)
        if len(token.box) != 4:
            return result(False, "every box is [x0, y0, x1, y1]", text=token.text, box=token.box)
        x0, y0, x1, y1 = token.box
        if not (0 <= x0 < x1 <= output_value.width and 0 <= y0 < y1 <= output_value.height):
            return result(False, "a word's box is not on the page", text=token.text, box=token.box)
    return result(True, "the receipt is scanned", path=output_value.path, tokens=len(tokens))
