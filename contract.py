"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    SCAN_RECEIPT = "scan_receipt"
    ANSWER_KEY = "answer_key"


class Task(Enum):
    FIND_TOP_ITEM = "find-top-item"


@dataclass
class ReceiptInput(Output):
    seed: Annotated[
        int, "Which receipt to scan: a whole number from 0 to 999999; the same seed always scans the same receipt"
    ]


@dataclass
class Token(Output):
    text: Annotated[str, "One word as OCR read it"]
    box: Annotated[list[int], "The word's bounding box [x0, y0, x1, y1] in pixels; y grows downward"]


@dataclass
class ScanOutput(Output):
    path: Annotated[str, "The scan's JSON file, relative to the workspace"]
    width: Annotated[int, "The page's width in pixels"]
    height: Annotated[int, "The page's height in pixels"]
    tokens: Annotated[list[Token], "Every word on the receipt with its bounding box, in no particular order"]
    question: Annotated[str, "The question to answer about the receipt"]


@dataclass
class Item(Output):
    name: Annotated[str, "The item's name as printed"]
    quantity: Annotated[int, "How many were bought"]
    unit_price: Annotated[str, "The price of one, in dollars with two decimals"]
    line_total: Annotated[str, "quantity × unit_price, in dollars with two decimals"]


@dataclass
class AnswerKeyOutput(Output):
    store: Annotated[str, "The store's name"]
    items: Annotated[list[Item], "The receipt's item lines, top to bottom"]
    subtotal: Annotated[str, "The sum of the line totals"]
    tax: Annotated[str, "The tax on the subtotal"]
    total: Annotated[str, "subtotal + tax"]
    item: Annotated[str, "The answer: the name of the item with the highest line total"]


@dataclass
class AnswerOutput(Output):
    item: Annotated[str, "The full name of the item with the highest line total, as printed on the receipt"]


TOOLS = {
    Tool.SCAN_RECEIPT: (ReceiptInput, ScanOutput),
    Tool.ANSWER_KEY: (ReceiptInput, AnswerKeyOutput),
}
TASKS = {Task.FIND_TOP_ITEM: (ReceiptInput, AnswerOutput)}
