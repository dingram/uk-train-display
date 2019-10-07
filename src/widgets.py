import datetime

from luma.core.virtual import snapshot

from PIL import Image
from PIL import ImageDraw


class TimeWidget(snapshot):
  """Widget for rendering the current time."""

  def __init__(self, resources):
    self._res = resources

    # Calculate how big we need to be.
    im = Image.new('1', (self._res.full_width, self._res.full_height))
    draw = ImageDraw.Draw(im)

    # Cache the text size for seconds so we don't have to keep recalculating
    # it. We use a static string because it updates frequently and we don't
    # want it to move around due to the difference in character widths.
    #
    # Ideally we want to be even more clever and keep all of the digits of
    # everything the same width, but that will take a little more effort. For
    # now, we accept that the hours/minutes can cause horizontal shifting.
    self._secs_w, self._secs_h = draw.textsize(':00', self._res.font_clock_secs)
    hhmm_w, hhmm_h = draw.textsize('00:00', self._res.font_clock_hhmm)

    del draw
    del im

    # Width/height should be 62/14, but it's better to calculate it.
    super().__init__(
        width=hhmm_w + self._secs_w,
        height=max(hhmm_h, self._secs_h),
        interval=0.1)

  def update(self, draw):
    now = datetime.datetime.now().time()
    hhmm = now.strftime('%H:%M')

    hhmm_w, hhmm_h = draw.textsize(hhmm, self._res.font_clock_hhmm)
    hhmm_xoffset = (self.width - hhmm_w - self._secs_w) // 2

    # Add masking rectangle, so we don't clash with anything underneath.
    draw.rectangle(
        [(0, 0), (self.width, self.height)], fill=self._res.background)
    draw.text(
        (hhmm_xoffset, 0),
        text=hhmm,
        font=self._res.font_clock_hhmm,
        fill='yellow')
    draw.text(
        (hhmm_xoffset + hhmm_w, self.height - self._secs_h),
        text=':{:02d}'.format(now.second),
        font=self._res.font_clock_secs,
        fill='yellow')


class OutOfHoursWidget(snapshot):
  """Widget for rendering the "out of hours" text."""
  WELCOME_TEXT = 'Welcome to'

  def __init__(self, resources, station_data, out_of_hours_name):
    self._res = resources
    self._data = station_data
    self._name = out_of_hours_name

    # Calculate how big we need to be.
    im = Image.new('1', (self._res.full_width, self._res.full_height))
    draw = ImageDraw.Draw(im)

    _, welcome_h = draw.textsize(self.WELCOME_TEXT, self._res.font_bold)
    # Use the maximum height of any letter, including ascenders and descenders.
    _, max_location_h = draw.textsize(
        '0123456789AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz',
        self._res.font_bold)

    del draw
    del im

    super().__init__(
        width=self._res.full_width,
        height=welcome_h + 2 + max_location_h,
        interval=60)

  def update(self, draw):
    location = self._name or self._data.station_name
    welcome_w, welcome_h = draw.textsize(self.WELCOME_TEXT, self._res.font_bold)
    location_w, location_h = draw.textsize(location, self._res.font_bold)

    draw.rectangle(
        [(0, 0), (self.width, self.height)], fill=self._res.background)
    draw.text(
        ((self.width - welcome_w) // 2, 0),
        text=self.WELCOME_TEXT,
        font=self._res.font_bold,
        fill='yellow')
    draw.text(
        ((self.width - location_w) // 2, welcome_h + 2),
        text=location,
        font=self._res.font_bold,
        fill='yellow')
