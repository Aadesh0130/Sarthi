import re
from fastapi import HTTPException, status


def normalize_and_validate_phone(phone: str) -> str:
    """
    Validates and normalizes phone number to E.164 format (+91XXXXXXXXXX).
    Supports Indian mobile numbers (10 digits, starts with 6, 7, 8, or 9).
    """
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required."
        )

    # Strip whitespaces, dashes, parentheses
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())

    # Handle standard formats:
    # 1) +91XXXXXXXXXX
    # 2) 91XXXXXXXXXX
    # 3) 0XXXXXXXXXX
    # 4) XXXXXXXXXX (10 digits)
    if cleaned.startswith("+91"):
        number_part = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        number_part = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        number_part = cleaned[1:]
    elif len(cleaned) == 10:
        number_part = cleaned
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format. Please provide a valid 10-digit mobile number."
        )

    # Indian mobile numbers must be 10 digits and start with 6, 7, 8, or 9
    if not re.match(r"^[6-9]\d{9}$", number_part):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Indian mobile number. It must be 10 digits starting with 6, 7, 8, or 9."
        )

    return f"+91{number_part}"
