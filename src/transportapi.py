import datetime
import enum
import io
import json
import os
import threading
import time
from typing import Collection

from absl import logging
import attr
import requests


class Error(Exception):
  pass


class DataError(Error):
  pass


@attr.s(frozen=True)
class Departure(object):

  @classmethod
  def from_json(cls, json) -> 'Departure':
    return json


@attr.s(frozen=True)
class DepartureResponse(object):
  date: str = attr.ib()
  time_of_day: str = attr.ib()
  request_time: str = attr.ib()
  station_name: str = attr.ib()
  station_code: str = attr.ib()
  all_departures: Collection[Departure] = attr.ib()

  @classmethod
  def from_json(cls, json) -> 'DepartureResponse':
    return json


class TransportApiClient(object):
  LIVE_URL = 'http://transportapi.com/v3/uk/train/station/{}/live.json'

  def __init__(self, api_key, app_id):
    self.api_key = api_key
    self.app_id = app_id

  def get_departures(self, station_code, calling_at=None, use_darwin=False):
    url = self.LIVE_URL.format(station_code)
    params = {
        'app_id': self.app_id,
        'app_key': self.api_key,
        'calling_at': calling_at,
        'darwin': use_darwin,
    }

    response = requests.get(url=url, params=params)
    result = response.json()

    if 'error' in result:
        raise DataError(result['error'])

    return DepartureResponse.from_json(result)

  def get_stops_from_departure(self, station_code, departure):
    timetable_url = departure['service_timetable']['id']
    response = requests.get(url=timetable_url)
    result = response.json()

    if 'error' in result:
        raise DataError(result['error'])

    # TODO: return type
    return result


class EmulatedTransportApiClient(object):
  BASE_DIR = os.path.join(
      os.path.abspath(os.path.dirname(os.path.dirname(__file__))), 'sampledata')

  def get_departures(self, station_code, calling_at=None, use_darwin=False):
    now = datetime.datetime.now()  # TODO: timezone aware, not naive

    if calling_at:
      filename = f'{station_code}-{calling_at}.json'
    else:
      filename = f'{station_code}.json'
    sample_path = os.path.join(self.BASE_DIR, 'departures', filename)

    if not os.path.exists(sample_path):
      raise DataError(
          f'No stored results for {filename.replace(".json", "")}')

    with io.open(sample_path, 'rt') as f:
      sample_departures = json.load(f)

    time.sleep(2)

    return DepartureResponse.from_json({
        'date': now.strftime('%Y-%m-%d'),
        'time_of_day': now.strftime('%H:%M'),
        'request_time': now.strftime('%Y-%m-%dT%H:%M:%S%z'), # TODO: timezone
        'station_name': f'Emulated {station_code}',
        'station_code': station_code,
        'departures': {
            'all': sample_departures,
        },
    })

  def get_stops_from_departure(self, station_code, departure):
    sample_path = os.path.join(self.BASE_DIR, 'timetables', 
                               f'{departure["train_uid"]}.json')

    if not os.path.exists(sample_path):
      raise DataError(
          f'No stored results for timetable {departure["train_uid"]}')

    with io.open(sample_path, 'rt') as f:
      sample_timetable = json.load(f)

    time.sleep(0.2)

    # TODO: return type
    return sample_timetable


class DataState(enum.IntEnum):
  UNINITIALIZED = 0
  LOADING = 1
  IDLE = 2
  ERROR = 3


class StationData(object):

  def __init__(self, api, station_code, calling_at=None, update_interval=None):
    self._api = api
    self._station_code = station_code
    self._station_name = 'Unknown Location'
    self._calling_at = calling_at
    self._update_interval = max(update_interval or 120, 15)

    self._lock = threading.RLock()
    self._last_update_counter = time.monotonic()
    self._last_update_time = time.time()
    self._departures = None
    self._timetables = {}
    self._state = DataState.UNINITIALIZED
    self._error = None

  def refresh_if_needed(self):
    if not self.needs_refresh():
      # Already processing a refresh, or data is fresh enough.
      return
    self._refresh()

  def force_refresh(self):
    self._refresh()

  def _refresh(self):
    with self._lock:
      self._state = DataState.LOADING
      try:
        self._refresh_departures()
      except Exception as e:
        logging.exception('Failed to fetch data')
        self._state = DataState.ERROR
        self._error = e
        return
      finally:
        self._last_update_counter = time.monotonic()
        self._last_update_time = time.time()
      self._state = DataState.IDLE

  def _refresh_departures(self):
    logging.info('Fetching departures %s-%s...', self._station_code,
                 self._calling_at)
    result = self._api.get_departures(
        self._station_code, calling_at=self._calling_at)

    self._departures = result['departures']['all']
    self._station_name = result['station_name']
    self._station_code = result['station_code']

  @property
  def seconds_since_update(self):
    return time.monotonic() - self._last_update_counter

  @property
  def refresh_interval(self):
    return self._update_interval

  @property
  def is_data_stale(self):
    return self.seconds_since_update > self._update_interval

  @property
  def state(self):
    return self._state

  def needs_refresh(self):
    if self._state == DataState.LOADING:
      return False
    return self.is_data_stale

  @property
  def calling_at(self):
    return self._calling_at

  @property
  def station_code(self):
    return self._station_code

  @property
  def station_name(self):
    return self._station_name

  @property
  def departures(self):
    return self._departures

  def get_timetable(self, departure):
    # TODO: cache results
    return self._api.get_stops_from_departure(
        self._station_code, departure)
