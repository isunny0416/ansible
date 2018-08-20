# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: ntnx_vm
short_description: create or cancel a virtual instance in Nutanix
description:
  - Creates or cancels Nutanix instances.
  - When created, optionally waits for it to be 'running'.
version_added: "1.0"
options:
  image:
    description:
      - Image Template to be used for new virtual instance.
  hostname:
    description:
      - Hostname to be provided to a virtual instance.
    required: true
  description:
    description:
      - description to be provided to a virtual instance.
  cores_per_vcpu:
    description:
      - Count of cores per vcpu to be assigned to new virtual instance.
    default: 1
  vcpu:
    description:
      - Count of cpu to be assigned to new virtual instance.
    default: 1
  memory:
    description:
      - Amount of memory to be assigned to new virtual instance.
      - Unit: Gigabyte
    default: 4
  disks:
    description:
      - a list of hash/dictionaries of volumes to add to the new instance; '[{"key":"value", "key":"value"}]'; 
        keys allowed are 
      - storage_name (str; required), device_index (int, list index num), device_bus (deprecated), size (int, GB)
  interfaces:
     description:
      - List of interface to be assigned to new virtual instance. 
  user_data:
    description:
      - opaque blob of data which is made available to the virtual instance
  state:
    description:
      - Create, or cancel a virtual instance.
      - Specify C(present) for create, C(absent) to cancel.
    choices: ['present', 'absent', 'started', 'restarted', 'stopped']
    default: present
requirements:
    - python >= 2.6
    - requests >= 2.9
author:
- Insun Kim (insun.kim@sk.com)
'''

EXAMPLES = '''
- name: Build instance
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Build instance request
      ntnx_vm:
        images: feaed57d-d35e-488c-988e-a3df00d045f9
        hostname: instance-1
        cores_per_vcpu: 1
        vcpus: 2
        memory: 4
        state: present

- name: Build instance Add Disks
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Build instance request
      ntnx_vm:
        images: feaed57d-d35e-488c-988e-a3df00d045f9
        hostname: instance-2
        cores_per_vcpu: 1
        vcpus: 2
        memory: 4
        disks:
          - storage_name: SelfServiceContainer
            device_bus: SCSI
            size: 50
        state: present

- name: Terminate instance
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Terminate instance request
      ntnx_vm:
        hostname: instance-2
        state: absent
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.nutanix import *
import traceback


class NtnxVm:

    def __init__(self, module):
        self.module = module
        self.client = NutanixClient(module)

    def vm_user_data(self, module):
        return '''
            #cloud-config
            hostname: {0}

            write_files:
              - path: /etc/sysconfig/network-scripts/ifcfg-eth0
                content: |
                  DEVICE=eth0
                  USERCTL=no
                  BOOTPROTO=static
                  IPADDR={1}
                  PREFIX=24
                  GATEWAY=172.21.89.1
                  ONBOOT=yes
                  TYPE=Ethernet
                  IPV6INIT=no
              - path: /etc/resolve.conf
                content: |
                  nameserver 172.21.91.20

            runcmd:
              - ifdown eth0
              - ifup eht0
        '''.format(module.params.get('hostname'), '172.21.89.213')

    def get_vm_instance(self, vm_uuid):
        uri = '/vms/{0}'.format(vm_uuid)
        payload = dict(
            include_vm_disk_config=True,
            include_vm_nic_config=True
        )
        return self.client.open_url(uri=uri, payload=payload)

    def get_vm_uuid_from_task(self, task_uuid):
        uri = '/tasks/{0}'.format(task_uuid)
        tasks = self.client.open_url(uri=uri)
        vm_uuid = tasks.get('entity_list')[0].get('entity_id')

        return vm_uuid

    def get_storage_uuid(self, storage_name):
        uri = '/storage_containers/'
        storages = self.client.open_url(uri=uri)
        storage = list(filter(lambda x: x.get('name') == storage_name, storages.get('entities')))

        return storage[0].get('storage_container_uuid')

    def is_vm_instance(self, module):
        uri = '/vms/'
        vms = self.client.open_url(uri=uri)
        instance = list(filter(lambda x: x.get('name') == module.params.get('hostname'), vms.get('entities')))
        if len(instance) == 1:
            is_instance = True
            vm_uuid = instance[0].get('uuid')

        elif len(instance) == 0:
            is_instance = False
            vm_uuid = None

        else:
            module.fail_json(msg='It does not exist or there are many instances of the same name.: {0}'.format(module.params.get('hostname')))

        return is_instance, vm_uuid

    def vm_power_state(self, current_power_state, vm_uuid, state):
        if current_power_state in ('off', 'OFF') and state in ('present', 'started'):
            transition = ('ON',)

        elif current_power_state in ('on', 'ON') and state == 'stopped':
            transition = ('OFF',)

        elif state == 'restarted':
            transition = ('OFF', 'ON')

        else:
            transition = ()

        for i in transition:
            uri = '/vms/{0}/set_power_state'.format(vm_uuid)
            self.client.open_url(method='post', uri=uri, payload=dict(transition=i))

    def detach_disk(self, vm_uuid, disks):
        pass

    def attach_disk(self, vm_uuid, current_disk_info, module):
        changed = False
        uri = '/vms/{0}/disks/attach'.format(vm_uuid)
        disks = module.params.get('disks')
        vm_disk_specs = [dict(
            is_cdrom=False,
            disk_address={
                'device_bus': 'SCSI',
                'device_index': i,
            },
            vm_disk_create={
                'storage_container_uuid': self.get_storage_uuid(disk.get('storage_name')),
                'size': (1024 ** 3) * disk.get('size')
            }
        ) for i, disk in enumerate(disks, start=1)]

        current_disk_len = len([i for i in current_disk_info if i.get('disk_address').get('device_bus') == 'scsi']) - 1

        del vm_disk_specs[0:current_disk_len]

        if vm_disk_specs:
            self.client.open_url(method='post', uri=uri, payload=dict(vm_disks=vm_disk_specs))
            changed = True

        return changed

    def detach_interface(self, vm_uuid, module):
        pass

    def attach_interface(self, vm_uuid, module):
        uri = '/vms/{0}/nics/'.format(vm_uuid)
        interfaces = module.params.get('interface')
        vm_interface_specs = [dict(
            is_cdrom=False,
            disk_address={'device_bus': interface.get('device_bus', 'scsi')},
            vm_disk_create={
                'storage_container_uuid': self.get_storage_uuid(interface.get('storage_name')),
                'size': (1024 ** 3) * interface.get('size')
            }
        ) for interface in interfaces]

        self.client.open_url(method='post', uri=uri, payload=dict(spec_list=[vm_interface_specs]))

    def delete_vm_instance(self, module):
        is_instance, vm_uuid = self.is_vm_instance(module)
        try:
            if is_instance:
                uri = '/vms/{0}'.format(vm_uuid)
                self.client.open_url(method='delete', uri=uri, payload=dict(delete_snapshots=True))
                return True, None

            else:
                module.fail_json(msg='There are instances that do not exist or are duplicates.: {0}'.format(module.params.get('hostname')))

        except HTTPError as e:
            module.fail_json(msg='Failed to get connectione: {0}'.format(e), exception=traceback.format_exc())

    def create_vm_instance(self, module):
        image = module.params.get('image')
        hostname = module.params.get('hostname')
        num_cores_per_vcpu = module.params.get('cores_per_vcpu')
        num_vcpus = module.params.get('vcpus')
        memory_mb = 1024 * module.params.get('memory')
        disks = module.params.get('disks')
        interfaces = module.params.get('interfaces')
        user_data = self.vm_user_data(module)
        state = module.params.get('state')
        vm_disk_info = []
        current_power_state = 'off'
        is_instance, vm_uuid = self.is_vm_instance(module)
        vm_spec = dict(
            name=hostname,
            num_cores_per_vcpu=num_cores_per_vcpu,
            num_vcpus=num_vcpus,
            memory_mb=memory_mb,
        )

        try:
            if is_instance:
                vm_instance = self.get_vm_instance(vm_uuid)
                current_power_state = vm_instance.get('power_state')
                for k, v in vm_instance.items():
                    if v == vm_spec.get(k, None):
                        del vm_spec[k]

                    if k == 'vm_disk_info':
                        vm_disk_info = v

                if vm_spec:
                    self.vm_power_state(current_power_state=current_power_state, vm_uuid=vm_uuid, state='stopped')
                    uri = '/vms/{0}'.format(vm_uuid)
                    self.client.open_url(method='put', uri=uri, payload=vm_spec)
                    changed = True

                else:
                    changed = False

            else:
                if image is None:
                    module.fail_json(msg='Instance creation requires image id')
                uri = '/vms/{0}/clone'.format(image)
                vm_spec.update({'userdata': user_data})
                task_info = self.client.open_url(method='post', uri=uri, payload=(dict(spec_list=[vm_spec])))
                vm_uuid = self.get_vm_uuid_from_task(task_info.get('task_uuid'))
                changed = True

            if disks:
                if self.attach_disk(vm_uuid=vm_uuid, current_disk_info=vm_disk_info, module=module):
                    changed = True

            if interfaces:
                self.attach_interface(vm_uuid=vm_uuid, module=module)

            self.vm_power_state(current_power_state=current_power_state, vm_uuid=vm_uuid, state=state)
            instance = self.get_vm_instance(vm_uuid)
            return changed, instance

        except HTTPError as e:
            module.fail_json(msg='{0}'.format(e), exception=traceback.format_exc())

        except RequestException as e:
            module.fail_json(msg='{0}'.format(e))


def main():
    argument_spec = ntnx_common_argument_spec()
    argument_spec.update(
        dict(
            image={'aliases': ['image_uuid'], 'default': None},
            hostname={'required': True},
            vm_id={'aliases': ['vm_uuid'], 'default': None},
            description={'required': False},
            cores_per_vcpu={'type': 'int', 'aliases': ['num_cores_per_vcpu'], 'default': 1},
            vcpus={'type': 'int', 'aliases': ['num_vcpu'], 'default': 2},
            memory={'type': 'int', 'aliases': ['memory_size'], 'default': 4},
            default_ip={'aliases': ['private_ip']},
            disks={'type': 'list', 'default': []},
            interfaces={'type': 'list', 'default': []},
            user_data={},
            state={'choices': ['present', 'absent', 'started', 'restarted', 'stopped'], 'default': 'present'},
            count={'type': 'int', 'default': 1}
        )
    )

    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_REQUESTS:
        module.fail_json(msg='requests required for this module')

    ntnx_vm = NtnxVm(module)

    if module.params.get('state') == 'absent':
        changed, instance = ntnx_vm.delete_vm_instance(module)

    else:
        changed, instance = ntnx_vm.create_vm_instance(module)

    module.exit_json(changed=changed, instance=instance)


if __name__ == '__main__':
    main()
