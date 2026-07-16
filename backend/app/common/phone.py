import re

_IRAN_E164 = re.compile(r"^\+989\d{9}$")


def normalize_iranian_mobile(raw: str) -> str:
    value = re.sub(r"[\s\-()]", "", raw)
    if value.startswith("0098"):
        value = "+98" + value[4:]
    elif value.startswith("98"):
        value = "+" + value
    elif value.startswith("09"):
        value = "+98" + value[1:]
    elif value.startswith("9"):
        value = "+98" + value
    if not _IRAN_E164.fullmatch(value):
        raise ValueError("mobile number must be a valid Iranian mobile number")
    return value
