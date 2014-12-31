#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: pkg5
author: Peter Oliver
short_description: Manages packages with the Solaris 11 Image Packaging System
description:
  - IPS packages are the native packages in Solaris 11 and higher.
notes:
  - The naming of IPS packages is explained at http://www.oracle.com/technetwork/articles/servers-storage-admin/ips-package-versioning-2232906.html.
options:
  name:
    description:
      - An FRMI of the package(s) to be installed/removed/updated.
      - Multiple packages may be specified, separated by C(,).  If C(,)
        appears in an FRMI, you can replace it with C(-).
    required: true
  state:
    description:
      - Whether to install (C(present), C(latest)), or remove (C(absent)) a
        package.
    required: false
    default: present
    choices: [ present, latest, absent ]
'''
EXAMPLES = '''
# Install Vim:
- pkg5: name=editor/vim

# Remove finger daemon:
- pkg5: name=service/network/finger state=absent
'''

def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(required=True, type='list'),
            state=dict(
                default='present',
                choices=[
                    'present',
                    'installed',
                    'latest',
                    'absent',
                    'uninstalled',
                    'removed',
                ]
            ),
        )
    )

    params = module.params
    if params['state'] in ['present', 'installed']:
        ensure(module, 'present', params['name'])
    elif params['state'] in ['latest']:
        ensure(module, 'latest', params['name'])
    elif params['state'] in ['absent', 'uninstalled', 'removed']:
        ensure(module, 'absent', params['name'])


def ensure(module, state, packages):
    response = {
        'results': [],
        'msg': '',
    }
    behaviour = {
        'present': {
            'filter': lambda p: not is_installed(module, p),
            'subcommand': 'install',
        },
        'latest': {
            'filter': lambda p: not is_latest(module, p),
            'subcommand': 'install',
        },
        'absent': {
            'filter': lambda p: is_installed(module, p),
            'subcommand': 'uninstall',
        },
    }

    to_modify = filter(behaviour[state]['filter'], packages)
    if to_modify:
        rc, out, err = module.run_command(
            ['pkg', behaviour[state]['subcommand'], '-q', '--'] + to_modify
        )
        response['rc'] = rc
        response['results'].append(out)
        response['msg'] += err
        response['changed'] = True
        if rc != 0:
            module.fail_json(**response)

    module.exit_json(**response)


def is_installed(module, package):
    rc, out, err = module.run_command(['pkg', 'list', '--', package])
    return True if rc == 0 else False


def is_latest(module, package):
    rc, out, err = module.run_command(['pkg', 'list', '-u', '--', package])
    return True if rc == 1 else False


from ansible.module_utils.basic import *
main()
