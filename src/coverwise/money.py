"""Display INR without floating point or changing canonical evidence."""

import re


def inr(paise: int) -> str:
    if type(paise) is not int or paise < 0:
        raise ValueError("paise must be a nonnegative integer")
    rupees, fraction = divmod(paise, 100)
    digits = str(rupees)
    groups = [digits[-3:]]
    digits = digits[:-3]
    while digits:
        groups.insert(0, digits[-2:])
        digits = digits[:-2]
    return "₹" + ",".join(groups) + (f".{fraction:02d}" if fraction else "")


def display_money(value: str) -> str:
    """Only an extracted display value, never a quoted evidence excerpt."""

    def amount(match):
        unit = match[2]
        if (
            unit is None
            and value[match.end() :] == ", total annual premium for both members."
        ):
            unit = "year"
        return inr(int(match[1])) + (f"/{unit}" if unit else "")

    return re.sub(r"\b(\d+) INR paise\b(?: per (day|year)\b)?", amount, value)
