import os

from absl import logging


DASHBOARD_URL_BASE = 'https://dashboard.balena-cloud.com'


class Error(Exception):
  pass


class NotRunningOnBalenaError(Error):
  """Raised when the app is not currently running on Balena."""


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
  def supervisor_port(self) -> str:
    return self._getenv('SUPERVISOR_PORT')

  @property
  def supervisor_version(self) -> str:
    return self._getenv('SUPERVISOR_VERSION')


class Balena(object):

  def __init__(self, environ=None):
    if environ is None:
      environ = os.environ
    self._env = BalenaEnvironment(environ)
    self._log_startup_message()

  def is_balena(self) -> bool:
    return self._env.is_balena

  @property
  def env(self):
    return self._env

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
