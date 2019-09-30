import datetime
import enum
from typing import Collection, Tuple

import attr


class Day(enum.Enum):
  MONDAY = 0
  TUESDAY = 1
  WEDNESDAY = 2
  THURSDAY = 3
  FRIDAY = 4
  SATURDAY = 5
  SUNDAY = 6
  DAILY = enum.auto()
  WEEKDAY = enum.auto()
  WEEKEND = enum.auto()

  def is_today(self, dt: datetime.datetime) -> bool:
    """Return whether this day is "today" for the given datetime."""

    if self is Day.DAILY:
      return True
    day = dt.weekday()
    if self is Day.WEEKDAY:
      return day < 5
    if self is Day.WEEKEND:
      return day >= 5
    return Day(day) == self

  def is_yesterday(self, dt: datetime.datetime) -> bool:
    """Return whether this day is "yesterday" for the given datetime."""
    return self.is_today(dt - datetime.timedelta(days=1))

  @staticmethod
  def parse(daystr: str) -> 'Day':
    daystr = daystr.lower()
    if daystr in ('mon', 'monday', 'mondays'):
      return Day.MONDAY
    elif daystr in ('tue', 'tues', 'tuesday', 'tuesdays'):
      return Day.TUESDAY
    elif daystr in ('wed', 'weds', 'wednesday', 'wednesdays'):
      return Day.WEDNESDAY
    elif daystr in ('thu', 'thurs', 'thursday', 'thursdays'):
      return Day.THURSDAY
    elif daystr in ('fri', 'friday', 'fridays'):
      return Day.FRIDAY
    elif daystr in ('sat', 'saturday', 'saturdays'):
      return Day.SATURDAY
    elif daystr in ('sun', 'sunday', 'sundays'):
      return Day.SUNDAY
    elif daystr in ('weekday', 'weekdays', 'week'):
      return Day.WEEKDAY
    elif daystr in ('weekend', 'weekends'):
      return Day.WEEKEND
    elif daystr in ('', 'all', 'daily', 'every', 'everyday'):
      return Day.DAILY
    raise ValueError('Unknown day %r' % daystr)


@attr.s(frozen=True)
class TimeRange(object):
  start: datetime.time = attr.ib()
  end: datetime.time = attr.ib()
  day: Day = attr.ib()

  def is_active(self, dt: datetime.datetime) -> bool:
    dt_time = dt.time()
    if self.start <= self.end:
      return self.day.is_today(dt) and self.start <= dt_time <= self.end
    else:
      return ((self.day.is_today(dt) and dt_time >= self.start) or
              (self.day.is_yesterday(dt) and dt_time <= self.end))

  @staticmethod
  def _parse_time(t: str) -> Tuple[int, int]:
    if not t.isdigit():
      raise ValueError('Invalid time %r: must be just digits' % t)
    hh, mm = 0, 0
    if len(t) > 2:
      hh = int(t[:-2], 10)
      mm = int(t[2:], 10)
    else:
      hh = int(t, 10)
    return hh, mm

  @classmethod
  def parse(cls, timerange: str) -> 'TimeRange':
    day_time = timerange.strip().split(':', 1)
    if (len(day_time) == 1 or day_time[0].isdigit() or
        day_time[0].replace('-', '').isdigit()):
      # Cope with no day, as well as mistaken colons e.g. "13:45-17:15".
      day = Day.DAILY
      timestr = ':'.join(day_time)
    else:
      day = Day.parse(day_time[0])
      timestr = day_time[1].replace(':', '')
    timestr = timestr.replace(':', '').replace('.', '')

    if '-' not in timestr:
      raise ValueError('Invalid time range %r: no dash found.' % timestr)
    start, end = timestr.split('-', 1)

    return cls(
        start=datetime.time(*cls._parse_time(start)),
        # Go right up to the end of the end minute.
        end=datetime.time(*cls._parse_time(end), second=59,
            microsecond=999999),
        day=day)


@attr.s(frozen=True)
class TimeRanges(object):
  ranges: Collection[TimeRange] = attr.ib()

  def __len__(self):
    return len(self.ranges)

  def __iter__(self):
    return iter(self.ranges)

  def is_active(self, dt: datetime.datetime) -> bool:
    for r in self.ranges:
      if r.is_active(dt):
        return True
    return False

  @classmethod
  def parse(cls, timeranges: str) -> 'TimeRanges':
    split_ranges = [r.strip() for r in timeranges.split(',')]
    ranges = [TimeRange.parse(r) for r in split_ranges if r]
    return cls(ranges)
