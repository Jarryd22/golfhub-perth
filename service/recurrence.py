"""Bounded calendar expansion. A repeating watch survives a closed phone."""
from datetime import date, timedelta


def recurrence_dates(raw, today, days=28):
    if not isinstance(raw, dict) or set(raw) != {'kind', 'anchor', 'weekday', 'day', 'ordinal'}:
        raise ValueError('recurrence')
    kind = raw['kind']
    if kind not in ('weekly', 'fortnightly', 'monthly_day', 'monthly_weekday'):
        raise ValueError('recurrence kind')
    anchor = date.fromisoformat(raw['anchor'])
    if anchor.isoformat() != raw['anchor']:
        raise ValueError('recurrence anchor')
    for name, maximum in [('weekday', 7), ('day', 31), ('ordinal', 5)]:
        if type(raw[name]) is not int or not 1 <= raw[name] <= maximum:
            raise ValueError('recurrence ' + name)
    week_start = anchor - timedelta(days=anchor.weekday())
    result = []
    for offset in range(days):
        d = today + timedelta(days=offset)
        if d < anchor:
            continue
        weekday = d.isoweekday() == raw['weekday']
        match = (weekday if kind == 'weekly' else
                 weekday and ((d - week_start).days // 7) % 2 == 0 if kind == 'fortnightly' else
                 d.day == raw['day'] if kind == 'monthly_day' else
                 weekday and ((d + timedelta(days=7)).month != d.month if raw['ordinal'] == 5
                              else (d.day - 1) // 7 + 1 == raw['ordinal']))
        if match:
            result.append(d.isoformat())
    return result


def sorted_dates(value):
    """Malformed client data never breaks other users' monitoring."""
    rows = value.get('dates', []) if isinstance(value, dict) else []
    if not isinstance(rows, list) or len(rows) > 28:
        return set()
    result = set()
    for d in rows:
        try:
            if isinstance(d, str) and date.fromisoformat(d).isoformat() == d:
                result.add(d)
        except ValueError:
            continue
    return result


def pending_rounds(spec, acknowledgements):
    dates = [d for d in spec['dates'] if d not in sorted_dates(acknowledgements)]
    # One upcoming round at a time. Once sorted, the next occurrence takes over.
    return dates[:1] if 'recurrence' in spec else dates
