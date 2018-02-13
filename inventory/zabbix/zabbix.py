#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2013, Greg Buehler
#
# This file is part of Ansible,
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

######################################################################

"""
Zabbix Server external inventory script.
========================================

Returns hosts and hostgroups from Zabbix Server.
If you want to run with --limit against a host group with space in the
name, use asterisk. For example --limit="Linux*servers".

Configuration is read from `zabbix.ini`.

Tested with Zabbix Server 2.0.6 and 3.2.3.
"""

from __future__ import print_function

import os
import sys
import argparse
import ConfigParser
import collections

from time import time

try:
    from zabbix_api import ZabbixAPI
except:
    print("Error: Zabbix API library must be installed: pip install zabbix-api.",
          file=sys.stderr)
    sys.exit(1)

try:
    import json
except:
    import simplejson as json


class ZabbixInventory(object):
    ansible_cache_path = '~/.ansible/tmp/'
    ansible_cache_max_age = 3600

    def read_settings(self):
        config = ConfigParser.SafeConfigParser()
        conf_path = './zabbix.ini'
        if not os.path.exists(conf_path):
            conf_path = os.path.dirname(os.path.realpath(__file__)) + '/zabbix.ini'
        if os.path.exists(conf_path):
            config.read(conf_path)
        # server
        if config.has_option('zabbix', 'server'):
            self.zabbix_server = config.get('zabbix', 'server')

        # login
        if config.has_option('zabbix', 'username'):
            self.zabbix_username = config.get('zabbix', 'username')
        if config.has_option('zabbix', 'password'):
            self.zabbix_password = config.get('zabbix', 'password')

        # inventory cache
        if config.has_option('ansible', 'cache_path'):
            self.ansible_cache_path = os.path.expanduser(config.get('ansible', 'cache_path'))
        if config.has_option('ansible', 'cache_max_age'):
            self.ansible_cache_max_age = config.get('ansible', 'cache_max_age')

    def read_cli(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('--host')
        parser.add_argument('--list', action='store_true')
        parser.add_argument('--refresh', action='store_true', default=False,
                            help='Force refresh of cache (default: use cache files)')

        self.options = parser.parse_args()

    def inventory_cache_valid(self, ansible_cache_file):
        if not os.path.isdir(self.ansible_cache_path):
            os.makedirs(self.ansible_cache_path)

        if os.path.isfile(ansible_cache_file):
            mod_time = os.path.getmtime(ansible_cache_file)
            current_time = time()
            return True if (mod_time + float(self.ansible_cache_max_age)) > current_time else False

        return False

    def get_inventory_cache(self, api, params):
        data = None
        ansible_cache_file = os.path.join(self.ansible_cache_path, 'ansible-inventory.cache')

        if self.inventory_cache_valid(ansible_cache_file) and not self.options.refresh:
            with open(ansible_cache_file, 'r') as f:
                data = json.loads(f.read())
        else:
            with open(ansible_cache_file, 'w+') as f:
                data = self.get_list(api, params)
                f.write(json.dumps(data, indent=2))

        return data

    def hoststub(self):
        return {
            'hosts': []
        }

    def get_host(self, api, ip, hostname=None):
        data = {
            'ansible_ssh_host': ip,
            'private_id': ip,
            'hostname': hostname
        }

        return data

    def get_list(self, api, params):
        hostsData = api.host.get(params)
        data = collections.OrderedDict()
        data[self.defaultgroup] = self.hoststub()

        for host in hostsData:
            hostname = host['name']
            ip = host['interfaces'][0]['ip']
            data[self.defaultgroup]['hosts'].append(ip)
            self.meta[ip] = self.get_host(api, ip, hostname)

            for group in host['groups']:
                groupname = group['name']

                if groupname not in data:
                    data[groupname] = self.hoststub()

                data[groupname]['hosts'].append(ip)

        # Prevents Ansible from calling this script for each server with --host
        data['_meta'] = {'hostvars': self.meta}

        return data

    def __init__(self):

        self.defaultgroup = 'group_all'
        self.zabbix_server = None
        self.zabbix_username = None
        self.zabbix_password = None
        self.meta = {}

        self.read_settings()
        self.read_cli()

        if self.zabbix_server and self.zabbix_username:
            try:
                api = ZabbixAPI(server=self.zabbix_server)
                api.login(user=self.zabbix_username, password=self.zabbix_password)
            except BaseException as e:
                print("Error: Could not login to Zabbix server. Check your zabbix.ini.",
                      file=sys.stderr)
                sys.exit(1)

            if self.options.host:
                data = self.get_host(api, self.options.host)
                print(json.dumps(data, indent=2))
            elif self.options.list:
                params = {
                    'output': 'extend',
                    'selectGroups': 'extend',
                    'selectInterfaces': ['ip'],
                    'selectParentTemplates': ['name']
                }
                data = self.get_inventory_cache(api, params)
                print(json.dumps(data, indent=2))
            else:
                print("usage: --list  ..OR.. --host <ip>", file=sys.stderr)
                sys.exit(1)

        else:
            print("Error: Configuration of server and credentials are required. See zabbix.ini.",
                  file=sys.stderr)
            sys.exit(1)

ZabbixInventory()
