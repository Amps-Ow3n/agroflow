from datetime import date, datetime, timedelta
def get_weeks_between(start_date, end_date):
    """
    Returns a list of ISO weeks (YYYY-Www) between start_date and end_date inclusive.
    """
    start_date = to_date(start_date)
    end_date = to_date(end_date)

    weeks = set()
    current = start_date
    while current <= end_date:
        year, week, _ = current.isocalendar()
        weeks.add(f"{year}-W{week:02d}")  # leading zero for ISO week
        current += timedelta(days=1)

    return sorted(list(weeks))

def to_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)

def to_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
