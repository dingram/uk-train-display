import os
from typing import Any, Collection, Mapping, Optional

from absl import logging
import requests


DASHBOARD_URL_BASE = 'https://dashboard.balena-cloud.com'
JsonDict = Mapping[str, Any]


class Error(Exception):
  pass


class NotRunningOnBalenaError(Error):
  """Raised when the app is not currently running on Balena."""


class SupervisorApiError(Error):
  """Raised when there was a problem talking to the supervisor."""


class BalenaEnvironment(object):

  def __init__(self, environ):
    # Freeze environment at initialization.
    self._environ = dict(environ)
    self._is_balena = (self._environ.get('BALENA', '0') == '1')

  def _check(self) -> None:
    if not self._is_balena:
      raise NotRunningOnBalenaError('Not running on Balena')

  def _getenv(self, varname: str) -> str:
    self._check()
    for prefix in ('BALENA', 'RESIN'):
      k = f'{prefix}_{varname.upper()}'
      if k in self._environ:
        return self._environ[k]
    return ''

  @property
  def is_balena(self) -> bool:
    return self._is_balena

  @property
  def api_key(self) -> str:
    return self._getenv('API_KEY')

  @property
  def api_url(self) -> str:
    return self._getenv('API_URL')

  @property
  def app_id(self) -> str:
    return self._getenv('APP_ID')

  @property
  def app_lock_path(self) -> str:
    return self._getenv('APP_LOCK_PATH')

  @property
  def app_name(self) -> str:
    return self._getenv('APP_NAME')

  @property
  def device_name_at_init(self) -> str:
    return self._getenv('DEVICE_NAME_AT_INIT')

  @property
  def device_type(self) -> str:
    return self._getenv('DEVICE_TYPE')

  @property
  def device_uuid(self) -> str:
    return self._getenv('DEVICE_UUID')

  @property
  def host_os_version(self) -> str:
    return self._getenv('HOST_OS_VERSION')

  @property
  def service_handover_complete_path(self) -> str:
    return self._getenv('SERVICE_HANDOVER_COMPLETE_PATH')

  @property
  def service_name(self) -> str:
    return self._getenv('SERVICE_NAME')

  @property
  def supervisor_address(self) -> str:
    return self._getenv('SUPERVISOR_ADDRESS')

  @property
  def supervisor_api_key(self) -> str:
    return self._getenv('SUPERVISOR_API_KEY')

  @property
  def supervisor_host(self) -> str:
    return self._getenv('SUPERVISOR_HOST')

  @property
  def supervisor_port(self) -> int:
    port = self._getenv('SUPERVISOR_PORT')
    if not port:
      return 0
    return int(port, 10)

  @property
  def supervisor_version(self) -> str:
    return self._getenv('SUPERVISOR_VERSION')


class BalenaSupervisor(object):

  def __init__(self, env: BalenaEnvironment):
    self._env = env
    self._base_url = env.supervisor_address
    self._api_key = env.supervisor_api_key

  def _request(self,
      method: str,
      endpoint: str,
      data: Optional[JsonDict] = None) -> requests.Response:
    if not data:
      data = {}

    params = {}
    if method.lower() == 'get':
      params.update(data)

    url = os.path.join(self._base_url, endpoint.lstrip('/'))
    params['apikey'] = self._api_key
    try:
      return requests.request(method, url=url, params=params, json=data)
    except Exception as e:
      raise SupervisorApiError(e)

  def ping(self) -> bool:
    response = self._request('get', '/ping')
    return response and response.text() == 'OK'

  def blink(self) -> None:
    self._request('post', '/v1/blink')

  def update(self, force: bool = False) -> None:
    self._request('post', '/v1/update', {
        'force': force,
    })

  def reboot(self, force: bool = False) -> None:
    self._request('post', '/v1/reboot', {
        'force': force,
    })

  def shutdown(self, force: bool = False) -> None:
    self._request('post', '/v1/shutdown', {
        'force': force,
    })

  def purge(self) -> None:
    self._request('post', '/v1/purge', {
        'appId': self._env.app_id,
    })

  def restart(self) -> None:
    self._request('post', '/v1/restart', {
        'appId': self._env.app_id,
    })

  def regenerate_api_key(self) -> None:
    self._api_key = self._request('post', '/v1/regenerate-api-key').text()

  def get_device(self) -> JsonDict:
    return self._request('get', '/v1/device').json()

  def stop_app(self) -> None:
    self._request('post', '/v1/apps/%s/stop' % self._env.app_id)

  def start_app(self) -> None:
    self._request('post', '/v1/apps/%s/start' % self._env.app_id)

  def get_app(self) -> JsonDict:
    return self._request('get', '/v1/apps/%s' % self._env.app_id).json()

  def get_healthy(self) -> bool:
    return self._request('get', '/v1/healthy').status_code == 200

  def get_applications_state(self) -> JsonDict:
    return self._request('get', '/v2/applications/state').json()

  def get_application_state(self) -> JsonDict:
    return self._request(
        'get', '/v2/applications/%s/state' % self._env.app_id).json()

  def get_status(self) -> JsonDict:
    return self._request('get', '/v2/state/status').json()

  def get_version(self) -> str:
    return self._request('get', '/v2/version').json()['version']

  def get_device_name(self) -> str:
    return self._request('get', '/v2/device/name').json()['deviceName']

  def get_device_tags(self) -> Collection[JsonDict]:
    return self._request('get', '/v2/device/tags').json()['tags']


class Balena(object):

  def __init__(self, environ=None):
    if environ is None:
      environ = os.environ
    self._env = BalenaEnvironment(environ)
    self._supervisor = None
    self._log_startup_message()

  def is_balena(self) -> bool:
    return self._env.is_balena

  @property
  def env(self) -> BalenaEnvironment:
    return self._env

  @property
  def supervisor(self) -> BalenaSupervisor:
    if not self._supervisor:
      self._supervisor = BalenaSupervisor(self._env)
    return self._supervisor

  def _log_startup_message(self):
    if not self.is_balena():
      logging.info('Not running on Balena.')
      return
    logging.info(
        'Running %s (ID %s) as Balena service %s',
        self._env.app_name,
        self._env.app_id,
        self._env.service_name)
    logging.info(
        'App URL: %s/apps/%s',
        DASHBOARD_URL_BASE,
        self._env.app_id)
    logging.info(
        'Host is %s device named %s (UUID %s) running %s',
        self._env.device_type,
        self._env.device_name_at_init,
        self._env.device_uuid,
        self._env.host_os_version)
    logging.info(
        'Device summary URL: %s/devices/%s/summary',
        DASHBOARD_URL_BASE,
        self._env.device_uuid)
