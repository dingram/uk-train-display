import datetime
import json
import os
import time
import threading

from absl import logging
from luma.core.render import canvas
from luma.core.sprite_system import framerate_regulator
from luma.core.virtual import snapshot
from luma.core.virtual import viewport
import PIL

import transportapi


WIDTH = 256
HEIGHT = 64


def _make_font(filename, pointsize):
    font_path = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'fonts',
            filename
        )
    )
    return PIL.ImageFont.truetype(font_path, pointsize)


class Controller(object):

  def __init__(self, device, station_data, out_of_hours_name, active_times,
      blank_times):
    self.device = device
    self.data = station_data
    self._out_of_hours_name = out_of_hours_name

    self._active_times = active_times
    self._blank_times = blank_times

    self.font_default = _make_font('Dot Matrix Regular.ttf', 10)
    self.font_bold = _make_font('Dot Matrix Bold.ttf', 10)
    self.font_clock_hhmm = _make_font('Dot Matrix Bold.ttf', 20)
    self.font_clock_secs = _make_font('Dot Matrix Bold Tall.ttf', 10)

    # Set up viewports.
    self._active_viewport = self.display_active()
    self._blank_viewport = self.display_blank()
    self._out_of_hours_viewport = self.display_out_of_hours()

    self.device.clear()

  def data_refresher(self):
    logging.info('Starting background data refresh...')
    while True:
      if self.is_active:
        self.data.refresh_if_needed()
      time.sleep(0.5)

  @property
  def is_active(self):
    now = datetime.datetime.now()
    return (not self._active_times) or self._active_times.is_active(now)

  @property
  def is_blank(self):
    now = datetime.datetime.now()
    return self._blank_times and self._blank_times.is_active(now)

  @property
  def is_out_of_hours(self):
    return (not self.is_active) and (not self.is_blank)

  def _render_centered_text(self, draw, text, font=None, y=None):
    if not font:
      font = self.font_default
    text_width, text_height = draw.textsize(text, font)
    if y is None:
      y = (self.device.height - text_height) // 2
    draw.text(
        ((self.device.width - text_width) // 2, y),
        text=text,
        font=self.font_bold,
        fill='yellow')

  def _hotspot_out_of_hours_static(self):
    def _render(draw, width, height):
      location = self._out_of_hours_name or self.data.station_name
      self._render_centered_text(draw, 'Welcome to', font=self.font_bold, y=0)
      self._render_centered_text(draw, location, font=self.font_bold, y=12)
    return snapshot(self.device.width, 20, _render, interval=10)

  def _hotspot_departure(self, idx):
    def _render(draw, width, height):
      deps = self.data.departures
      if idx >= len(deps):
        return
      font = self.font_default if idx else self.font_bold
      dep = deps[idx]
      departureTime = dep['aimed_departure_time']
      dest = dep['destination_name']
      draw.text((0, 0), text=f'{departureTime}  {dest}', font=font,
                fill='yellow')

      status = '???'
      if dep['status'] == 'CANCELLED':
        status = 'CANCELLED'
      elif dep['aimed_departure_time'] == dep['expected_departure_time']:
        status = 'On time'
      elif dep.get('expected_departure_time'):
        status = f'Exp {dep["expected_departure_time"]}'
      status = f'  {status}'

      w, _ = draw.textsize(status, font)
      # Ensure we do not overlap with the station.
      draw.rectangle([(width - w, 0), (width, height)], fill='black')
      draw.text((width - w, 0), text=status, font=font, fill='yellow')

    return snapshot(self.device.width, 12, _render, interval=10)

  def _hotspot_calling_at(self, idx):
    def _render(draw, width, height):
      pass
    return snapshot(self.device.width, 12, _render, interval=0.1)

  def _hotspot_data_status(self):
    def _render(draw, width, height):
      sigil = '?'
      state = self.data.state
      if state == transportapi.DataState.IDLE:
        sigil = '.'
      elif state == transportapi.DataState.LOADING:
        sigil = '*'
      elif state == transportapi.DataState.ERROR:
        sigil = '!'
      elif self.data.is_stale:
        sigil = 'z'
      w, _ = draw.textsize(sigil, self.font_default)
      draw.text((12 - w, 0), text=sigil, font=self.font_default, fill='yellow')
    return snapshot(12, 10, _render, interval=0.1)

  def _hotspot_time(self):
    def _render(draw, width, height):
      now = datetime.datetime.now().time()
      hhmm = now.strftime('%H:%M')

      # Use hardcoded text for seconds to avoid the text moving around due to
      # differences in character widths.
      secs_w, secs_h = draw.textsize(':00', self.font_clock_secs)
      hhmm_w, hhmm_h = draw.textsize(hhmm, self.font_clock_hhmm)
      hhmm_xoffset = (self.device.width - hhmm_w - secs_w) // 2

      draw.text(
          (hhmm_xoffset, 0),
          text=hhmm,
          font=self.font_clock_hhmm,
          fill='yellow')
      draw.text(
          (hhmm_xoffset + hhmm_w, hhmm_h - secs_h),
          text=':{:02d}'.format(now.second),
          font=self.font_clock_secs,
          fill='yellow')
    return snapshot(self.device.width - 16, 14, _render, interval=0.1)

  def display_active(self):
    view = viewport(self.device, self.device.width, self.device.height)

    view.add_hotspot(self._hotspot_departure(0), (0, 0))
    view.add_hotspot(self._hotspot_calling_at(0), (0, 12))
    view.add_hotspot(self._hotspot_departure(1), (0, 24))
    view.add_hotspot(self._hotspot_departure(2), (0, 36))
    view.add_hotspot(self._hotspot_time(), (0, 50))
    view.add_hotspot(
        self._hotspot_data_status(),
        (self.device.width - 12, self.device.height - 10))
    return view

  def display_blank(self):
    return viewport(self.device, self.device.width, self.device.height)

  def display_out_of_hours(self):
    view = viewport(self.device, self.device.width, self.device.height)
    if self._out_of_hours_name not in ('_blank_', '_clock_'):
      view.add_hotspot(self._hotspot_out_of_hours_static(), (0, 0))
    if self._out_of_hours_name != '_blank_':
      view.add_hotspot(self._hotspot_time(), (0, 50))
    return view

  @property
  def _current_viewport(self):
    if self.is_blank:
      return self._blank_viewport
    elif self.is_active:
      return self._active_viewport
    else:
      return self._out_of_hours_viewport

  def run_forever(self):
    if self._active_times:
      logging.info('Active times:\n    %s' % '\n    '.join(
          ('%r' % t) for t in self._active_times))
    if self._blank_times:
      logging.info('Blank times:\n    %s' % '\n    '.join(
          ('%r' % t) for t in self._blank_times))

    logging.info('Loading...')
    with canvas(self.device) as draw:
      self._render_centered_text(draw, 'Loading...', font=self.font_bold)

    async_refresh = threading.Thread(target=self.data_refresher, daemon=True)
    self.data.force_refresh()
    logging.info('First data loaded; starting real display')
    async_refresh.start()

    regulator = framerate_regulator(fps=10)

    while True:
      if self.is_active:
        # TODO: make this asynchronous
        self.data.refresh_if_needed()

      with regulator:
        self._current_viewport.refresh()
