import abc
import datetime
from typing import Tuple

from luma.core.virtual import snapshot

from PIL import Image
from PIL import ImageDraw

import transportapi


class Widget(snapshot, metaclass=abc.ABCMeta):
  """Base widget class."""

  def __init__(self, resources, interval):
    self._res = resources
    width, height = self._get_max_size()
    super().__init__(width=width, height=height, interval=interval)

  @abc.abstractmethod
  def _get_max_size(self) -> Tuple[int, int]:
    ...

  def update(self, draw):
    # Mask out the background to be sure the widget doesn't clash with anything
    # underneath.
    draw.rectangle(
        [(0, 0), (self.width, self.height)], fill=self._res.widget_background)
    self._update(draw)

  def preferred_position(self, host) -> Tuple[int, int]:
    raise NotImplementedError(
        'No preferred position for %s' % self.__class__.__name__)

  def add_to(self, viewport, device=None):
    viewport.add_hotspot(self, self.preferred_position(device or viewport))


class TimeWidget(Widget):
  """Widget for rendering the current time."""

  def __init__(self, resources):
    super().__init__(resources, interval=0.1)

  def _get_max_size(self):
    # Cache the text size for seconds so we don't have to keep recalculating
    # it. We use a static string because it updates frequently and we don't
    # want it to move around due to the difference in character widths.
    #
    # Ideally we want to be even more clever and keep all of the digits of
    # everything the same width, but that will take a little more effort. For
    # now, we accept that the hours/minutes can cause horizontal shifting.
    self._secs_w, self._secs_h = self._res.textsize(
        ':00', self._res.font_clock_secs)
    hhmm_w, hhmm_h = self._res.textsize('00:00', self._res.font_clock_hhmm)

    # Width/height should be 62/14, but it's better to calculate it.
    return hhmm_w + self._secs_w, max(hhmm_h, self._secs_h)

  def _update(self, draw):
    now = datetime.datetime.now().time()
    hhmm = now.strftime('%H:%M')

    hhmm_w, hhmm_h = self._res.textsize(hhmm, self._res.font_clock_hhmm)
    hhmm_xoffset = (self.width - hhmm_w - self._secs_w) // 2

    self._res.text(
        draw, (hhmm_xoffset, 0), hhmm, font=self._res.font_clock_hhmm)
    self._res.text(
        draw,
        (hhmm_xoffset + hhmm_w, self.height - self._secs_h),
        ':{:02d}'.format(now.second),
        font=self._res.font_clock_secs)

  def preferred_position(self, host):
    return ((host.width - self.width) // 2, host.height - self.height)


class OutOfHoursWidget(Widget):
  """Widget for rendering the "out of hours" text."""
  WELCOME_TEXT = 'Welcome to'
  LINE_SEP = 2

  def __init__(self, resources, station_data, out_of_hours_name):
    super().__init__(resources, interval=60)
    self._data = station_data
    self._name = out_of_hours_name

  def _get_max_size(self):
    _, welcome_h = self._res.textsize(self.WELCOME_TEXT, self._res.font_bold)
    # Use the maximum height of any letter, including ascenders and descenders.
    max_location_h = self._res.line_height(self._res.font_bold)

    return self._res.full_width, welcome_h + self.LINE_SEP + max_location_h

  def _update(self, draw):
    location = self._name or self._data.station_name
    welcome_w, welcome_h = self._res.textsize(
        self.WELCOME_TEXT, self._res.font_bold)
    location_w, location_h = self._res.textsize(location, self._res.font_bold)

    self._res.text(
        draw,
        ((self.width - welcome_w) // 2, 0),
        self.WELCOME_TEXT,
        font=self._res.font_bold)
    self._res.text(
        draw,
        ((self.width - location_w) // 2, welcome_h + self.LINE_SEP),
        location,
        font=self._res.font_bold)

  def preferred_position(self, host):
    return 0, 0


class DepartureWidget(Widget):
  """Widget for rendering a single departure line."""

  def __init__(self, resources, station_data, departure_index, show_platform):
    self.__font = None
    self._data = station_data
    self._index = departure_index
    self._show_platform = show_platform
    super().__init__(resources, interval=0.1)

  @property
  def _font(self):
    if self.__font is None:
      if self._index == 0:
        self.__font = self._res.font_bold
      else:
        self.__font = self._res.font_default
    return self.__font

  def _get_max_size(self):
    return self._res.full_width, self._res.line_height(self._font)

  def _update(self, draw):
    deps = self._data.departures
    if self._index >= len(deps):
      return
    dep = deps[self._index]

    scheduled_time = dep['aimed_departure_time']
    destination = dep['destination_name']
    platform = None
    if self._show_platform:
      if dep['mode'] == 'bus':
        platform = 'BUS'
      else:
        platform = dep.get('platform')
    status = self._get_status(dep)

    scheduled_time_w, _ = self._res.textsize('00:00', self._font)
    max_destination_w, _ = self._res.textsize(destination, self._font)
    if platform:
      platform_w, _ = self._res.textsize(platform, self._font)
      max_platform_w, _ = self._res.textsize('00', self._res.font_bold)
      max_platform_w = max(platform_w, max_platform_w)
    else:
      platform_w = 0
      max_platform_w = 0
    status_w, _ = self._res.textsize(status, self._font)
    max_status_w, _ = self._res.textsize('CANCELLED', self._font)

    scheduled_time_w += 1
    status_w += 1
    max_status_w += 1
    if platform:
      max_platform_w += 2

    destination_w = (
        self.width - scheduled_time_w - max_platform_w - max_status_w)

    # Actually render the line.
    self._res.text(draw, (0, 0), text=scheduled_time, font=self._font)
    self._res.text(
        draw, (scheduled_time_w, 0), text=destination, font=self._font)
    self._res.text(
        draw, (self.width - status_w - max_platform_w, 0), text=status,
        font=self._font, mask=True)
    if platform:
      self._res.text(
          draw, (self.width - platform_w, 0),
          text=platform, font=self._font, mask=True)

  def _get_status(self, dep):
    status = dep['status']
    if (dep.get('expected_departure_time') and
        dep['expected_departure_time'] != dep['aimed_departure_time']):
      status = f'Exp {dep["expected_departure_time"]}'

    # Reformat some statuses.
    on_time_statuses = {
        'CHANGE OF IDENTITY',
        'CHANGE OF ORIGIN',
        'EARLY',
        'NO REPORT',
        'OFF ROUTE',
        'ON TIME',
        'REINSTATEMENT',
        'STARTS HERE',
    }
    if status in on_time_statuses:
      status = 'On time'
    elif status == 'LATE':
      status = 'DELAYED'

    return status


class CallingAtWidget(Widget):
  """Widget for rendering a single "calling at" line."""
  CALLING_AT_TEXT = 'Calling at:'

  def __init__(self, resources, station_data, departure_index):
    super().__init__(resources, interval=0.1)
    self._data = station_data
    self._index = departure_index

  def _get_max_size(self):
    return self._res.full_width, self._res.line_height()

  def _update(self, draw):
    self._res.text(draw, (0, 0), self.CALLING_AT_TEXT)


class DataStatusWidget(Widget):
  """Widget for rendering the current train data status."""

  def __init__(self, resources, station_data, show_update_countdown):
    super().__init__(resources, interval=0.1)
    self._data = station_data
    self._show_update_countdown = show_update_countdown

  def _get_max_size(self):
    return 12, 12

  def _update(self, draw):
    state = self._data.state
    if state == transportapi.DataState.IDLE and self._show_update_countdown:
      fraction_until_refresh = (
          self._data.seconds_since_update / self._data.refresh_interval)
      if fraction_until_refresh < 0.01:
        draw.ellipse(
            [(0, 0), (self.width - 1, self.height - 1)],
            width=0,
            fill=self._res.foreground)
      elif fraction_until_refresh < 1:
        draw.pieslice(
            [(0, 0), (self.width - 1, self.height - 1)],
            width=0,
            fill=self._res.foreground,
            start=(360 * fraction_until_refresh) - 90,
            end=-90)
    else:
      sigil = '?'
      if state == transportapi.DataState.IDLE:
        sigil = '.'
      elif state == transportapi.DataState.LOADING:
        sigil = self._res.icon_loading
      elif state == transportapi.DataState.ERROR:
        sigil = self._res.icon_error
      elif self._data.is_stale:
        sigil = 'z'
      if isinstance(sigil, str):
        w, h = self._res.textsize(sigil, self._res.font_default)
        self._res.text(draw, (self.width - w, self.height - h), sigil)
      else:
        draw.bitmap((0, 0), sigil, fill=self._res.foreground)

  def preferred_position(self, host):
    return (host.width - self.width, host.height - self.height)
