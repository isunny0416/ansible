# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.six import with_metaclass
from configparser import NoSectionError, NoOptionError
import configparser
import os

try:
    import requests
    from requests import HTTPError, RequestException
    HAS_REQUESTS = True

except ImportError:
    HAS_REQUESTS = False


class Singleton(type):
    _instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance


class Configuration:

    def __init__(self):
        try:
            config = configparser.ConfigParser(allow_no_value=True)
            config.read(os.path.join(os.getenv('HOME'), '.nutanix'))
            section = os.getenv('NUTANIX_HOST') if os.getenv('NUTANIX_HOST') else 'defaults'
            self.default_url = config.get(section, 'default_url', fallback=None)
            self.user_name = config.get(section, 'user_name', fallback=None)
            self.user_password = config.get(section, 'user_password', fallback=None)
            self.headers = {'Content-Type': 'application/json'}
            self.verify = False

        except NoSectionError:
            pass

        except NoOptionError:
            pass


class NutanixClient(with_metaclass(Singleton, object)):

    def __init__(self, module):
        super(NutanixClient, self).__init__()
        self._config = Configuration()
        self.default_url = module.params.get('default_url')
        self.user_name = module.params.get('user_name')
        self.user_password = module.params.get('user_password')
        self.verify = module.params.get('verify')
        self.validate_params(module)
        self._session = self.get_ntnx_connection_info()

    def raise_for_task_result(self, task_uuid):
        uri = '/tasks/{0}'.format(task_uuid)
        url = '{0}{1}'.format(self.default_url, uri)
        r = self._session.get(url)
        r.raise_for_status()
        task = r.json()
        if task.get('meta_response', None) is not None:
            if task.get('meta_response').get('error_code') > 0:
                raise RequestException(task.get('meta_response').get('error_detail'))

    def open_url(self, method='get', uri=None, payload=dict()):
        url = '{0}{1}'.format(self.default_url, uri)
        if method == 'get':
            r = getattr(self._session, method)(url, params=payload, timeout=5)

        else:
            r = getattr(self._session, method)(url, json=payload, timeout=5)

        r.raise_for_status()
        data = r.json()
        if data.get('task_uuid', None) is not None:
            self.raise_for_task_result(data.get('task_uuid'))

        return data

    def validate_params(self, module):
        if self.default_url is None:
            if os.environ.get('NUTANIX_DEFAULT_URL'):
                self.default_url = os.environ.get('NUTANIX_DEFAULT_URL')

            elif self._config.default_url:
                self.default_url = self._config.default_url

            else:
                module.fail_json(msg='Undefined default url')

        if self.user_name is None:
            if os.environ.get('NUTANIX_USER_NAME'):
                self.user_name = os.environ.get('NUTANIX_USER_NAME')

            elif self._config.user_name:
                self.user_name = self._config.user_name

            else:
                module.fail_json(msg='Undefined user name')

        if self.user_password is None:
            if os.environ.get('NUTANIX_USER_PASSWORD'):
                self.user_password = os.environ.get('NUTANIX_USER_PASSWORD')

            elif self._config.user_password:
                self.user_password = self._config.user_password

            else:
                module.fail_json(msg='Undefined user password')

    def get_ntnx_connection_info(self):

        # Check module args for credentials, then check environment var

        headers = {'Content-Type': 'application/json'}
        s = requests.Session()
        s.auth = (self.user_name, self.user_password)
        s.verify = self.verify
        s.headers.update(headers)
        return s


def ntnx_common_argument_spec():
    return dict(
        user_name={'aliases': ['id', 'user'], 'no_log': True, 'default': None},
        user_password={'aliases': ['password', 'pwd'], 'no_log': True, 'default': None},
        url={'no_log': True, 'default': None},
        verify={'type': 'bool', 'no_log': True, 'default': False},
    )
