# backend/app/utils/date_utils.py

from datetime import datetime

def parse_date(date_string: str):
    return datetime.strptime(
        date_string,
        "%Y-%m-%d"
    ).date()

def is_within_window(
    source_start,
    source_end,
    target_start,
    target_end
):
    """
    Checks overlap between source availability
    and commitment delivery window.
    """

    return (
        source_start <= target_end
        and source_end >= target_start
    )