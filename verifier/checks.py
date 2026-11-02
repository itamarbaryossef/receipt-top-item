"""Checks shared by the tool verifiers. Pure functions of their arguments."""

SEEDS = 1_000_000  # a seed is in range(SEEDS), as src/plugin/receipt.py draws them


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def seed_problem(seed):
    if not 0 <= seed < SEEDS:
        return f"seed must be from 0 to {SEEDS - 1}, not {seed}"
    return None


def verify_seed(value):
    """verify_input of both tools: their input is only a seed."""
    problem = seed_problem(value.seed)
    if problem:
        return result(False, problem)
    return result(True, "input is valid")
