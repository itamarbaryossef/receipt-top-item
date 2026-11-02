"""answer_key, the task's reference, and the task itself: the agent's item against the pinned key."""

import re
from decimal import ROUND_HALF_UP, Decimal

from .checks import result, verify_seed

ITEMS = (4, 8)  # fewest and most item lines
QUANTITIES = (1, 5)
CENTS = (49, 1999)  # cheapest and dearest unit price, in cents
TAX_RATE = Decimal("0.0825")
MONEY = re.compile(r"\d+\.\d\d")  # dollars, always with two decimals


def verify_input(value):
    return verify_seed(value)


def verify_output(input_value, output_value, workspace):
    problem = key_problem(output_value)
    if problem:
        return result(False, problem)
    return result(True, "the answer key follows from the receipt", item=output_value.item)


def name_key(name):
    """A name as compared: ignoring case and the spaces around and between its words."""
    return " ".join(name.split()).casefold()


def key_problem(key):
    """What is wrong with ``key`` as a consistent receipt with one unambiguous top item, or None."""
    lines = key.items
    if not ITEMS[0] <= len(lines) <= ITEMS[1]:
        return f"the receipt has {len(lines)} items"
    if len({name_key(line.name) for line in lines}) != len(lines):
        return "two items share a name"
    amounts = [line.unit_price for line in lines] + [line.line_total for line in lines]
    if not all(MONEY.fullmatch(amount) for amount in [*amounts, key.subtotal, key.tax, key.total]):
        return "an amount is not dollars with two decimals"
    for line in lines:
        unit_price = Decimal(line.unit_price)
        if not QUANTITIES[0] <= line.quantity <= QUANTITIES[1] or not CENTS[0] <= unit_price * 100 <= CENTS[1]:
            return f"{line.name}'s quantity or unit price is out of range"
        if Decimal(line.line_total) != line.quantity * unit_price:
            return f"{line.name}'s line total is not its quantity times its unit price"
    subtotal = sum((Decimal(line.line_total) for line in lines), Decimal("0.00"))
    tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if Decimal(key.subtotal) != subtotal or Decimal(key.tax) != tax or Decimal(key.total) != subtotal + tax:
        return "the subtotal, tax and total do not add up"
    by_total = sorted(lines, key=lambda line: Decimal(line.line_total), reverse=True)
    by_price = sorted(lines, key=lambda line: Decimal(line.unit_price), reverse=True)
    if by_total[0].line_total == by_total[1].line_total or by_price[0].unit_price == by_price[1].unit_price:
        return "two items tie for the highest line total or unit price"
    if by_price[0] is by_total[0]:
        return "the item with the highest line total also has the highest unit price"
    if by_total[0] in (lines[0], lines[-1]):
        return "the item with the highest line total is the first or last line"
    if key.item != by_total[0].name:
        return f"the key's answer is not the receipt's: {by_total[0].name}"
    return None


def verify_task(arguments, output, reference, workspace):
    if reference is None:
        return result(False, "there is no answer key to check against")
    problem = key_problem(reference)
    if problem:
        return result(False, f"the answer key is unusable: {problem}")
    if not name_key(output.item):
        return result(False, "the answer names no item", given=output.item)
    lines = {name_key(line.name): line for line in reference.items}
    line = lines.get(name_key(output.item))
    if line is None:
        return result(
            False, f"{output.item!r} is not an item on the receipt", given=output.item, expected=reference.item
        )
    top = lines[name_key(reference.item)]
    if line is not top:
        highest_price = max(reference.items, key=lambda each: Decimal(each.unit_price))
        return result(
            False,
            f"{line.name} does not have the highest line total",
            given=output.item,
            expected=reference.item,
            given_line_total=line.line_total,
            expected_line_total=top.line_total,
            given_has_highest_unit_price=line is highest_price,
        )
    return result(True, f"{line.name} has the highest line total", given=output.item, expected=reference.item)
