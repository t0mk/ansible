#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2014, Sebastien Rohaut <sebastien.rohaut@gmail.com>
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

import os
import os.path
import shutil
import re

DOCUMENTATION = '''
---
module: pam_limits
version_added: "2.0"
short_description: Modify Linux PAM limits
description:
     - The M(pam_limits) module modify PAM limits, default in /etc/security/limits.conf.
       For the full documentation, see man limits.conf(5).
options:
  domain:
    description:
      - A username, @groupname, wildcard, uid/gid range.
    required: true
  limit_type:
    description:
      - Limit type, see C(man limits) for an explanation
    required: true
    choices: [ "hard", "soft" ]
  limit_item:
    description:
      - The limit to be set
    required: true
    choices: [ "core", "data", "fsize", "memlock", "nofile", "rss", "stack", "cpu", "nproc", "as", "maxlogins", "maxsyslogins", "priority", "locks", "sigpending", "msgqueue", "nice", "rtprio", "chroot" ]
  value:
    description:
      - The value of the limit.
    required: true
  backup:
    description:
      - Create a backup file including the timestamp information so you can get
        the original file back if you somehow clobbered it incorrectly.
    required: false
    choices: [ "yes", "no" ]
    default: "no"
  use_min:
    description:
      - If set to C(yes), the minimal value will be used or conserved.
        If the specified value is inferior to the value in the file, file content is replaced with the new value,
        else content is not modified.
    required: false
    choices: [ "yes", "no" ]
    default: "no"
  use_max:
    description:
      - If set to C(yes), the maximal value will be used or conserved.
        If the specified value is superior to the value in the file, file content is replaced with the new value,
        else content is not modified.
    required: false
    choices: [ "yes", "no" ]
    default: "no"
  dest:
    description:
      - Modify the limits.conf path.
    required: false
    default: "/etc/security/limits.conf"
'''

EXAMPLES = '''
# Add or modify limits for the user joe
- pam_limits: domain=joe limit_type=soft limit_item=nofile value=64000

# Add or modify limits for the user joe. Keep or set the maximal value
- pam_limits: domain=joe limit_type=soft limit_item=nofile value=1000000
'''

def main():

    pam_items = [ 'core', 'data', 'fsize', 'memlock', 'nofile', 'rss', 'stack', 'cpu', 'nproc', 'as', 'maxlogins', 'maxsyslogins', 'priority', 'locks', 'sigpending', 'msgqueue', 'nice', 'rtprio', 'chroot' ]

    pam_types = [ 'soft', 'hard', '-' ]

    limits_conf = '/home/slyce/limits.conf'

    module = AnsibleModule(
        # not checking because of daisy chain to file module
        argument_spec = dict(
            domain            = dict(required=True, type='str'),
            limit_type        = dict(required=True, type='str', choices=pam_types),
            limit_item        = dict(required=True, type='str', choices=pam_items),
            value             = dict(required=True, type='str'),
            use_max           = dict(default=False, type='bool'),
            use_min           = dict(default=False, type='bool'),
            backup            = dict(default=False, type='bool'),
            dest              = dict(default=limits_conf, type='str')
        )
    )

    domain      =       module.params['domain']
    limit_type  =       module.params['limit_type']
    limit_item  =       module.params['limit_item']
    value       =       module.params['value']
    use_max     =       module.params['use_max']
    use_min     =       module.params['use_min']
    backup      =       module.params['backup']
    limits_conf =       module.params['dest']

    changed = False

    if os.path.isfile(limits_conf):
        if not os.access(limits_conf, os.W_OK):
            module.fail_json(msg="%s is not writable. Use sudo" % (limits_conf) )
    else:
        module.fail_json(msg="%s is not visible (check presence, access rights, use sudo)" % (limits_conf) )

    if use_max and use_min:
        module.fail_json(msg="Cannot use use_min and use_max at the same time." )

    if not (value in ['unlimited', 'infinity', '-1'] or value.isdigit()):
        module.fail_json(msg="Argument 'value' can be one of 'unlimited', 'infinity', '-1' or positive number. Refer to manual pages for more details.")

    # Backup
    if backup:
        backup_file = module.backup_local(limits_conf)

    space_pattern = re.compile(r'\s+')

    message = ''
        f = open (limits_conf, 'r')
    # Tempfile
    nf = tempfile.NamedTemporaryFile(delete = False)

    found = False
    new_value       = value

    for line in f:
        if line.startswith('#'):
            nf.write(line)
            continue

        newline = re.sub(space_pattern, ' ', line).strip()
        if not newline:
            nf.write(line)
            continue

        line_fields = newline.split(' ')

        if len(line_fields) != 4:
            nf.write(line)
            continue

        line_domain     = line_fields[0]
        line_type       = line_fields[1]
        line_item       = line_fields[2]
        actual_value    = line_fields[3]

        if not (actual_value in ['unlimited', 'infinity', '-1'] or actual_value.isdigit()):
            module.fail_json(msg="Invalid configuration of '%s'. Current value of %s is unsupported." % (limits_conf, line_item))

        # Found the line
        if line_domain == domain and line_type == limit_type and line_item == limit_item:
            found = True
            if value == actual_value:
                message = line
                nf.write(line)
                continue

            actual_value_unlimited = actual_value in ['unlimited', 'infinity', '-1']
            value_unlimited = value in ['unlimited', 'infinity', '-1']

            if use_max:
                if value.isdigit() and actual_value.isdigit():
                    new_value = max(int(value), int(actual_value))
                elif actual_value_unlimited:
                    new_value = actual_value
                else:
                    new_value = value

            if use_min:
                if value.isdigit() and actual_value.isdigit():
                    new_value = min(int(value), int(actual_value))
                elif value_unlimited:
                    new_value = actual_value
                else:
                    new_value = value

            # Change line only if value has changed
            if new_value != actual_value:
                changed = True
                new_limit = domain + "\t" + limit_type + "\t" + limit_item + "\t" + str(new_value) + "\n"
                message = new_limit
                nf.write(new_limit)
            else:
                message = line
                nf.write(line)
        else:
            nf.write(line)

    if not found:
        changed = True
        new_limit = domain + "\t" + limit_type + "\t" + limit_item + "\t" + str(new_value) + "\n"
        message = new_limit
        nf.write(new_limit)

    f.close()
    nf.close()

    # Copy tempfile to newfile
    module.atomic_move(nf.name, f.name)

    res_args = dict(
        changed = changed, msg = message
    )

    if backup:
        res_args['backup_file'] = backup_file

    module.exit_json(**res_args)


# import module snippets
from ansible.module_utils.basic import *
main()
