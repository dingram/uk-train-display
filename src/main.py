import io
import json
import os
import signal
import sys

from absl import app
from absl import flags
from absl import logging

from luma.core.interface.serial import spi
from luma.oled.device import ssd1322

try:
  # Not expected to be available on the device, so make it an optional import.
  from luma.emulator.device import pygame
except ImportError:
  pygame = None

import display
import timerange
import transportapi


FLAGS = flags.FLAGS


flags.DEFINE_string('active_times', '',
                    'One or more time ranges during which the display will '
                    'show train departures.')
flags.DEFINE_string('blank_times', '',
                    'One or more time ranges during which the display will be '
                    'entirely blank. Takes precedence over active times.')
flags.DEFINE_string('calling_at', None,
                    'A National Rail code for a station that a train must call '
                    'at in order to be shown.')
flags.DEFINE_string('depart_from', None,
                    'The National Rail station code to show departures for.')
flags.DEFINE_integer('display_rotation', 0,
                     'Number of degrees to rotate the display. Must be either '
                     '0 or 180.')
flags.DEFINE_bool('emulate_api', False,
                  'Whether to emulate the Transport API for local development.')
flags.DEFINE_bool('emulate_display', False,
                  'Whether to emulate the display for local development.')
flags.DEFINE_integer('min_departure_min', 0,
                     'Minimum number of minutes until departure. Trains '
                     'departing sooner than this will not be shown.')
flags.DEFINE_string('out_of_hours_name', None,
                    'Name shown when outside active hours. If set to '
                    '"_clock_", the display will just show the current time. '
                    'If set to "_blank_", the display will be completely '
                    'blanked.')
flags.DEFINE_string('platform', None,
                    'The platform that trains must depart from in order to be '
                    'shown.')
flags.DEFINE_integer('refresh_interval', 120,
                     'Number of seconds between data refreshes.')
flags.DEFINE_multi_string('slow_stations', [],
                          'One or more National Rail station codes that, if '
                          'called at, cause a train to be be marked as "slow".')
flags.DEFINE_string('transport_api_app_id', None,
                  'Your app ID for the Transport API. If not given, this will '
                  'be read from the config.json file in the current directory.')
flags.DEFINE_string('transport_api_key', None,
                  'Your key for the Transport API. If not given, this will be '
                  'read from the config.json file in the current directory.')
flags.DEFINE_bool('show_calling_at', True,
                  'Whether to show the "calling at" line or an extra '
                  'departure.')
flags.DEFINE_bool('show_update_countdown', False,
                  'Whether to show an indicator of how long until the data is '
                  'refreshed.')


def init_emulated_display():
  logging.debug('Using emulated display; ignoring any rotation')
  if not pygame:
    raise app.UsageError(
        'Required luma/pygame dependency not found. Please make sure you '
        'have installed the required libraries and "emu" extras with pip')
  return pygame(width=display.WIDTH, height=display.HEIGHT)


def init_physical_display(rotation_deg):
  logging.debug('Using physical display, rotated %d degrees', rotation_deg)
  if rotation_deg not in (0, 180):
    raise app.UsageError(
        'Display rotation must be either 0 or 180 degrees.')

  serial = spi()
  return ssd1322(serial,
      mode='1',  # Use monochrome rendering rather than RGB -> greyscale.
      rotate=2 if rotation_deg == 180 else 0,
      width=display.WIDTH,
      height=display.HEIGHT)


def init_emulated_api():
  return transportapi.EmulatedTransportApiClient()


def init_real_api(api_key, app_id):
  if not api_key or not app_id:
    # Read from JSON file.
    with io.open('config.json', 'rt', encoding='utf-8') as f:
      config_json = json.load(f)
    if not api_key:
      api_key = config_json['transport_api']['api_key']
    if not app_id:
      app_id = config_json['transport_api']['app_id']

  return transportapi.TransportApiClient(api_key=api_key, app_id=app_id)


def _handle_sigterm(*args):
  logging.info('Received SIGTERM')
  raise KeyboardInterrupt


def main(argv):
  del argv
  for i, arg in enumerate(sys.argv[1:], start=1):
    logging.info('argv[%d]: %s', i, arg)

  if FLAGS.emulate_display:
    device = init_emulated_display()
  else:
    device = init_physical_display(FLAGS.display_rotation)

  if FLAGS.emulate_api:
    api_impl = init_emulated_api()
  else:
    api_impl = init_real_api(
        FLAGS.transport_api_key, FLAGS.transport_api_app_id)

  station_data = transportapi.StationData(api_impl, FLAGS.depart_from,
      calling_at=FLAGS.calling_at, update_interval=FLAGS.refresh_interval)
  controller = display.Controller(
      device,
      station_data,
      out_of_hours_name=FLAGS.out_of_hours_name,
      active_times=timerange.TimeRanges.parse(FLAGS.active_times,
          default_active=True),
      blank_times=timerange.TimeRanges.parse(FLAGS.blank_times),
      show_calling_at=FLAGS.show_calling_at,
      show_update_countdown=FLAGS.show_update_countdown,
  )

  logging.info('Setting up SIGTERM handler')
  signal.signal(signal.SIGTERM, _handle_sigterm)

  try:
    logging.info('Running controller')
    controller.run_forever()
  except KeyboardInterrupt:
    pass
  logging.info('Shutting down...')
  device.clear()
  device.cleanup()
  logging.info('Shutdown complete.')


if __name__ == '__main__':
  flags.mark_flag_as_required('depart_from')
  app.run(main)
