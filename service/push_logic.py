"""Pure matching and replay protection for the cloud availability checker."""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.cache_schema import MAX_FRESH_AGE_SECONDS, timestamp
from service.recurrence import recurrence_dates

PERTH = ZoneInfo('Australia/Perth')


def validate_watch(raw, catalog, now):
    today = now.astimezone(PERTH).date()
    if raw.get('enabled') is not True:
        raise ValueError('disabled')
    fields = ('dates', 'course_ids', 'holes', 'players', 'from_minutes', 'to_minutes')
    spec = {k: raw[k] for k in fields}
    if type(raw.get('notify_existing', False)) is not bool:
        raise ValueError('notify_existing')
    spec['notify_existing'] = raw.get('notify_existing', False)
    if 'recurrence' in raw:
        spec['recurrence'] = raw['recurrence']
        spec['dates'] = recurrence_dates(raw['recurrence'], today)
    quiet = [raw.get('quiet_from_minutes'), raw.get('quiet_to_minutes')]
    if any(v is not None for v in quiet):
        if any(type(v) is not int or not 0 <= v < 1440 for v in quiet) or quiet[0] == quiet[1]:
            raise ValueError('quiet hours')
        spec.update(quiet_from_minutes=quiet[0], quiet_to_minutes=quiet[1])
    for key, maximum in [('dates', 28), ('course_ids', 50)]:
        minimum = 0 if key == 'dates' and 'recurrence' in spec else 1
        if not isinstance(spec[key], list) or not minimum <= len(spec[key]) <= maximum:
            raise ValueError(key)
        if any(not isinstance(v, str) for v in spec[key]):
            raise ValueError(key)
        spec[key] = sorted(set(spec[key]))
    if type(spec['holes']) is not int or spec['holes'] not in (9, 18):
        raise ValueError('holes')
    if type(spec['players']) is not int or not 1 <= spec['players'] <= 4:
        raise ValueError('players')
    low, high = spec['from_minutes'], spec['to_minutes']
    if type(low) is not int or type(high) is not int or not 0 <= low <= high < 1440:
        raise ValueError('time')
    for day in spec['dates']:
        parsed = date.fromisoformat(day)
        if parsed.isoformat() != day or parsed >= today + timedelta(days=28):
            raise ValueError('date')
    if any(c not in catalog.courses or spec['holes'] not in catalog.courses[c]['holes'] for c in spec['course_ids']):
        raise ValueError('course')
    # Passed dates are discarded without losing the remaining preferred dates.
    spec['dates'] = [d for d in spec['dates'] if d >= today.isoformat()]
    return spec


def quiet_now(spec, now):
    low, high = spec.get('quiet_from_minutes'), spec.get('quiet_to_minutes')
    if low is None or high is None or low == high:
        return False
    local = now.astimezone(PERTH)
    minute = local.hour * 60 + local.minute
    return low <= minute < high if low < high else minute >= low or minute < high


def delivery_ttl(spec, now):
    """Do not leave an offline push queued past the next quiet-hours boundary."""
    if quiet_now(spec, now):
        return 0
    low = spec.get('quiet_from_minutes')
    if low is None:
        return 600
    local = now.astimezone(PERTH)
    boundary = local.replace(hour=low // 60, minute=low % 60, second=0, microsecond=0)
    if boundary <= local:
        boundary += timedelta(days=1)
    return min(600, max(0, int((boundary - local).total_seconds())))


def generation(raw):
    # Re-enabling an alert creates a new baseline, even for identical filters.
    return hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:24]


def slot_key(tee):
    return json.dumps([tee['minutes'], tee.get('course') or ''], separators=(',', ':'))


def valid_matches(course, day, now):
    stamp = timestamp(course.get('checked_at'))
    if (course.get('status') not in ('available', 'no_matching_times')
        or course.get('freshness') != 'fresh' or stamp is None
        or not -60 <= (now - stamp).total_seconds() < MAX_FRESH_AGE_SECONDS):
        return None
    result = []
    for tee in course['times']:
        start = datetime.combine(date.fromisoformat(day), datetime.min.time(), PERTH) + timedelta(minutes=tee['minutes'])
        if start > now:
            result.append(tee)
    return result


def transition(previous, course, day, now, notify_existing=False):
    """Alert on an opening, including a previously full slot becoming available.

    Unknown/stale checks preserve the last known availability. Upgrading old
    'seen' state establishes a quiet current baseline to avoid a migration flood.
    """
    matches = valid_matches(course, day, now)
    if matches is None:
        return previous, []
    checked = timestamp(course['checked_at'])
    if previous and timestamp(previous['checked_at']) >= checked:
        return previous, []
    current = {slot_key(t) for t in matches}
    if previous is None:
        new = matches if notify_existing else []
    elif 'available' not in previous:
        new = []
    else:
        old = set(previous['available'])
        new = [t for t in matches if slot_key(t) not in old]
    if len(current) > 2000:
        # Keep Firestore documents bounded and fail visibly instead of repeating alerts.
        raise ValueError('Too many tee times in one course/day')
    return {'checked_at': checked.isoformat(), 'available': sorted(current)}, new


def event_id(path, generation_id, matches):
    return hashlib.sha256(json.dumps([path, generation_id, matches], sort_keys=True).encode()).hexdigest()[:32]
