import datetime
import enum
import os
import time
import threading

from absl import logging
from luma.core.render import canvas
from luma.core.sprite_system import framerate_regulator
from luma.core.virtual import snapshot
from luma.core.virtual import viewport
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageOps

import widgets


WIDTH = 256
HEIGHT = 64


class DisplayState(enum.Enum):
  ACTIVE = enum.auto()
  BLANK = enum.auto()
  OUT_OF_HOURS = enum.auto()


class Resources(object):

  def __init__(self):
    self.full_width = WIDTH
    self.full_height = HEIGHT
    self.background = 'black'
    self.widget_background = 'black'
    self.foreground = '#f8c41b'

    self.font_default = self._load_font('Dot Matrix Regular.ttf', 10)
    self.font_bold = self._load_font('Dot Matrix Bold.ttf', 10)
    self.font_clock_hhmm = self._load_font('Dot Matrix Bold.ttf', 20)
    self.font_clock_secs = self._load_font('Dot Matrix Bold Tall.ttf', 10)

    self.icon_error = self._load_icon('status-error.png')
    self.icon_loading = self._load_icon('status-loading.png')

    self._im = Image.new('1', (self.full_width, self.full_height))
    self._draw = ImageDraw.Draw(self._im)

  @staticmethod
  def _load_font(filename, pointsize):
    font_path = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'fonts',
            filename
        )
    )
    return ImageFont.truetype(font_path, pointsize)

  @staticmethod
  def _load_icon(filename):
    icon_path = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'icons',
            filename
        )
    )
    img = Image.open(icon_path)
    img = img.convert('L')
    img = ImageOps.invert(img)
    img = img.convert('1')
    return img

  def line_height(self, font=None):
    # Use the maximum height of any letter, including ascenders and descenders.
    _, max_h = self.textsize(
        '0123456789AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz',
        font or self.font_default)
    return max_h

  def text(self, draw, pos, text, font=None, mask=False):
    """Convenience function for rendering text."""
    if not font:
      font = self.font_default
    x, y = pos
    if mask:
      w, h = draw.textsize(text, font)
      draw.rectangle([(x, y), (x + w, y + h)], fill=self.background)
    draw.text(
        (x, y),
        text=text,
        font=font or self.font_default,
        fill=self.foreground)

  def textsize(self, text, font=None):
    """Convenience function to avoid creating images to measure text."""
    return self._draw.textsize(text, font or self.font_default)


class Controller(object):

  def __init__(self, device, station_data, balena_info, out_of_hours_name,
      active_times, blank_times, show_calling_at, show_update_countdown):
    self.device = device
    self.data = station_data
    self.balena = balena_info
    self._out_of_hours_name = out_of_hours_name
    self._show_calling_at = show_calling_at
    self._show_update_countdown = show_update_countdown

    self._active_times = active_times
    self._blank_times = blank_times

    self._res = Resources()

    # Set up available viewports.
    self._active_viewport = self.display_active()
    self._blank_viewport = self.display_blank()
    self._out_of_hours_viewport = self.display_out_of_hours()

    # Set up current state.
    self._viewport = None
    self._current_display_state = None
    self.update_display_state()

    self.device.clear()

  def data_refresher(self):
    logging.info('Starting background data refresh every %d seconds...',
        self.data.refresh_interval)
    while True:
      if self.is_active() or self.is_active_soon():
        self.data.refresh_if_needed()
      time.sleep(0.5)

  def get_display_state(self, when=None):
    if not when:
      when = datetime.datetime.now()
    if self._blank_times and self._blank_times.is_active(when):
      return DisplayState.BLANK
    elif (not self._active_times) or self._active_times.is_active(when):
      return DisplayState.ACTIVE
    return DisplayState.OUT_OF_HOURS

  @property
  def display_state(self):
    return self.get_display_state()

  def is_active(self):
    return self.display_state == DisplayState.ACTIVE

  def is_active_soon(self):
    # Return True if we are going to become active within two refresh
    # intervals.
    when = datetime.datetime.now()
    when += datetime.timedelta(seconds=self.data.refresh_interval * 2)
    return self.get_display_state(when) == DisplayState.ACTIVE

  def is_blank(self):
    return self.display_state == DisplayState.BLANK

  def is_out_of_hours(self):
    return self.display_state == DisplayState.OUT_OF_HOURS

  def _render_centered_text(self, draw, text, font=None, y=None):
    if not font:
      font = self._res.font_default
    text_width, text_height = self._res.textsize(text, font)
    if y is None:
      y = (self.device.height - text_height) // 2
    self._res.text(
        draw, ((self.device.width - text_width) // 2, y), text, font=font)

  def _hotspot_departure(self, idx):
    def _render(draw, width, height):
      deps = self.data.departures
      if idx >= len(deps):
        return
      font = self._res.font_default if idx else self._res.font_bold
      dep = deps[idx]
      departureTime = dep['aimed_departure_time']
      dest = dep['destination_name']
      self._res.text(draw, (0, 0), text=f'{departureTime}  {dest}', font=font)

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

      status = f'  {status}'
      w, _ = self._res.textsize(status, font)
      # Mask the text so the output does not overlap with the station.
      self._res.text(draw, (width - w, 0), text=status, font=font, mask=True)

    return snapshot(self.device.width, 12, _render, interval=10)

  def _hotspot_calling_at(self, idx):
    def _render(draw, width, height):
      pass
    return snapshot(self.device.width, 12, _render, interval=0.1)

  def display_active(self):
    view = viewport(self.device, self.device.width, self.device.height)

    view.add_hotspot(self._hotspot_departure(0), (0, 0))
    if self._show_calling_at:
      view.add_hotspot(self._hotspot_calling_at(0), (0, 12))
      view.add_hotspot(self._hotspot_departure(1), (0, 24))
      view.add_hotspot(self._hotspot_departure(2), (0, 36))
    else:
      view.add_hotspot(self._hotspot_departure(1), (0, 12))
      view.add_hotspot(self._hotspot_departure(2), (0, 24))
      view.add_hotspot(self._hotspot_departure(3), (0, 36))

    widgets.TimeWidget(self._res).add_to(view, device=self.device)
    data_widget = widgets.DataStatusWidget(
        self._res, self.data, self._show_update_countdown)
    data_widget.add_to(view, device=self.device)
    return view

  def display_blank(self):
    return viewport(self.device, self.device.width, self.device.height)

  def display_out_of_hours(self):
    view = viewport(self.device, self.device.width, self.device.height)
    if self._out_of_hours_name not in ('_blank_', '_clock_'):
      ooh_widget = widgets.OutOfHoursWidget(
          self._res, self.data, self._out_of_hours_name)
      ooh_widget.add_to(view, device=self.device)
    if self._out_of_hours_name != '_blank_':
      widgets.TimeWidget(self._res).add_to(view, device=self.device)

    return view

  def update_display_state(self):
    current_state = self.display_state
    if self._viewport and self._current_display_state == current_state:
      return

    logging.info('Transitioning display to %s', current_state.name)
    self._current_display_state = current_state
    if current_state == DisplayState.BLANK:
      self._viewport = self._blank_viewport
    elif current_state == DisplayState.ACTIVE:
      self._viewport = self._active_viewport
    else:
      self._viewport = self._out_of_hours_viewport

  def run_forever(self):
    if self._active_times:
      logging.info('Active times:\n  %s' % '\n  '.join(
          ('%s' % t) for t in self._active_times))
    if self._blank_times:
      logging.info('Blank times:\n  %s' % '\n  '.join(
          ('%s' % t) for t in self._blank_times))

    logging.info('Loading...')
    with canvas(self.device) as draw:
      self._render_centered_text(draw, 'Loading...', font=self._res.font_bold)

    async_refresh = threading.Thread(target=self.data_refresher, daemon=True)
    self.data.force_refresh()
    logging.info('First data loaded; starting real display')
    async_refresh.start()

    regulator = framerate_regulator(fps=10)

    while True:
      with regulator:
        self.update_display_state()
        self._viewport.refresh()
