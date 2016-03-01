#!/usr/bin/python
#
# This file is part of Ansible
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
#
DOCUMENTATION = """
---
module: junos_template
version_added: "2.1"
author: "Peter sprygada (@privateip)"
short_description: Manage Juniper JUNOS device configurations
description:
  - Manages network device configurations over SSH.  This module
    allows implementors to work with the device configuration.  It
    provides a way to push a set of commands onto a network device
    by evaluting the current configuration and only pushing
    commands that are not already configured.
extends_documentation_fragment: junos
options:
  src:
    description:
      - The path to the config source.  The source can be either a
        file with config or a template that will be merged during
        runtime.  By default the task will search for the source
        file in role or playbook root folder in templates directory.
    required: false
    default: null
  force:
    description:
      - The force argument instructs the module to not consider the
        current devices configuration.  When set to true, this will
        cause the module to push the contents of I(src) into the device
        without first checking if already configured.
    required: false
    default: false
    choices: [ "true", "false" ]
  backup:
    description:
      - When this argument is configured true, the module will backup
        the configuration from the node prior to making any changes.
        The backup file will be written to backup_{{ hostname }} in
        the root of the playbook directory.
    required: false
    default: false
    choices: [ "true", "false" ]
  config:
    description:
      - The module, by default, will connect to the remote device and
        retrieve the current configuration to use as a base for comparing
        against the contents of source.  There are times when it is not
        desirable to have the task get the current configuration for
        every task in a playbook.  The I(config) argument allows the
        implementer to pass in the configuruation to use as the base
        config for comparision.
    required: false
    default: null
"""

EXAMPLES = """

- name: push a configuration onto the device
  junos_template:
    src: config.j2

- name: forceable push a configuration onto the device
  junos_template:
    src: config.j2
    force: yes

- name: provide the base configuration for comparision
  junos_template:
    src: candidate_config.txt
    config: current_config.txt

"""

RETURN = """

commands:
  description: The set of commands that will be pushed to the remote device
  returned: always
  type: list
  sample: [...]

"""

def compare(this, other):
    parents = [item.text for item in this.parents]
    for entry in other:
        if this == entry:
            return None
    return this

def expand(obj, action='set'):
    cmd = [action]
    cmd.extend([p.text for p in obj.parents])
    cmd.append(obj.text)
    return ' '.join(cmd)

def flatten(data, obj):
    for k, v in data.items():
        obj.append(k)
        flatten(v, obj)
    return obj

def to_lines(config):
    lines = list()
    for item in config:
        if item.raw.endswith(';'):
            line = [p.text for p in item.parents]
            line.append(item.text)
            lines.append(' '.join(line))
    return lines

def get_config(module):
    config = module.params['config'] or list()
    if not config and not module.params['force']:
        config = module.config
    return config

def main():
    """ main entry point for module execution
    """

    argument_spec = dict(
        src=dict(),
        force=dict(default=False, type='bool'),
        backup=dict(default=False, type='bool'),
        config=dict(),
    )

    mutually_exclusive = [('config', 'backup'), ('config', 'force')]

    module = get_module(argument_spec=argument_spec,
                        mutually_exclusive=mutually_exclusive,
                        supports_check_mode=True)

    result = dict(changed=False)

    parsed = module.parse_config(module.params['src'])
    commands = to_lines(parsed)

    contents = get_config(module)
    result['_backup'] = module.config

    parsed = module.parse_config(contents)
    config = to_lines(parsed)

    candidate = list()
    for item in commands:
        if item not in config:
            candidate.append('set %s' % item)

    if candidate:
        if not module.check_mode:
            module.configure(candidate)
        result['changed'] = True

    result['updates'] = candidate
    return module.exit_json(**result)


from ansible.module_utils.basic import *
from ansible.module_utils.shell import *
from ansible.module_utils.netcfg import *
from ansible.module_utils.junos import *
if __name__ == '__main__':
    main()
