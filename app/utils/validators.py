"""Input validation & parsing helpers for user-typed commands."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.models.loan import LOAN_TYPE_LEND, LOAN_TYPE_OWE

MAX_DESCRIPTION_LENGTH = 500
MAX_PERSON_NAME_LENGTH = 255
MAX_AMOUNT = Decimal("999999999")

_DURATION_UNIT_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7,
    "month": 30, "months": 30,
    "year": 365, "years": 365,
}

# "/loan lend 50000 Khasan 1 month" or "/loan owe 500000 Dad" (no due date)
_LOAN_PATTERN = re.compile(
    r"^(?P<type>lend|owe)\s+(?P<amount>[\d.,]+)\s+"
    r"(?P<rest>.+)$",
    re.IGNORECASE,
)
_TRAILING_DURATION = re.compile(
    r"^(?P<name>.+?)\s+(?P<number>\d+)\s+(?P<unit>day|days|week|weeks|month|months|year|years)$",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """Raised when user input fails validation; message is safe to show the user."""


@dataclass
class ParsedLoan:
    type: str
    amount: Decimal
    person_name: str
    due_date: date | None


def validate_amount(raw: str | float | int | Decimal) -> Decimal:
    try:
        amount = Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValidationError(f"'{raw}' doesn't look like a valid amount.") from exc

    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if amount > MAX_AMOUNT:
        raise ValidationError(f"Amount is too large (max {MAX_AMOUNT}).")
    return amount


def sanitize_text(text: str | None, max_length: int = MAX_DESCRIPTION_LENGTH) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    return cleaned[:max_length]


def parse_loan_command(args: str) -> ParsedLoan:
    """Parse `<lend|owe> <amount> <person name...> [<N> <day|week|month|year>[s]]`."""
    if not args or not args.strip():
        raise ValidationError(
            "Usage: /loan <lend|owe> <amount> <person name> [<N> <day|week|month|year>]\n"
            "Example: /loan lend 50000 Khasan 1 month"
        )

    match = _LOAN_PATTERN.match(args.strip())
    if not match:
        raise ValidationError(
            "Couldn't understand that. Usage:\n"
            "/loan <lend|owe> <amount> <person name> [<N> <day|week|month|year>]\n"
            "Example: /loan lend 50000 Khasan 1 month"
        )

    loan_type = LOAN_TYPE_LEND if match.group("type").lower() == "lend" else LOAN_TYPE_OWE
    amount = validate_amount(match.group("amount"))
    rest = match.group("rest").strip()

    duration_match = _TRAILING_DURATION.match(rest)
    if duration_match:
        person_name = duration_match.group("name").strip()
        number = int(duration_match.group("number"))
        unit = duration_match.group("unit").lower()
        due_date = date.today() + timedelta(days=number * _DURATION_UNIT_DAYS[unit])
    else:
        person_name = rest
        due_date = None

    person_name = sanitize_text(person_name, MAX_PERSON_NAME_LENGTH)
    if not person_name:
        raise ValidationError("Please include the person's name.")

    return ParsedLoan(type=loan_type, amount=amount, person_name=person_name, due_date=due_date)
