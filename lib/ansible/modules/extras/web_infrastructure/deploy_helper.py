#!/usr/bin/python

DOCUMENTATION = '''
---
module: deploy_helper
version_added: "1.8"
author: Ramon de la Fuente, Jasper N. Brouwer
short_description: Manages some of the steps common in deploying projects.
description:
  - The Deploy Helper manages some of the steps common in deploying software.
    It creates a folder structure, manages a symlink for the current release
    and cleans up old releases.
  - "Running it with the C(state=query) or C(state=present) will return the C(deploy_helper) fact.
    C(project_path), whatever you set in the path parameter,
    C(current_path), the path to the symlink that points to the active release,
    C(releases_path), the path to the folder to keep releases in,
    C(shared_path), the path to the folder to keep shared resources in,
    C(unfinished_filename), the file to check for to recognize unfinished builds,
    C(previous_release), the release the 'current' symlink is pointing to,
    C(previous_release_path), the full path to the 'current' symlink target,
    C(new_release), either the 'release' parameter or a generated timestamp,
    C(new_release_path), the path to the new release folder (not created by the module)."

options:
  path:
    required: true
    aliases: ['dest']
    description:
      - the root path of the project. Alias I(dest).
        Returned in the C(deploy_helper.project_path) fact.

  state:
    required: false
    choices: [ present, finalize, absent, clean, query ]
    default: present
    description:
      - the state of the project.
        C(query) will only gather facts,
        C(present) will create the project I(root) folder, and in it the I(releases) and I(shared) folders,
        C(finalize) will remove the unfinished_filename file, create a symlink to the newly
          deployed release and optionally clean old releases,
        C(clean) will remove failed & old releases,
        C(absent) will remove the project folder (synonymous to the M(file) module with C(state=absent))

  release:
    required: false
    description:
      - the release version that is being deployed. Defaults to a timestamp format %Y%m%d%H%M%S (i.e. '20141119223359').
        This parameter is optional during C(state=present), but needs to be set explicitly for C(state=finalize).
        You can use the generated fact C(release={{ deploy_helper.new_release }}).

  releases_path:
    required: false
    default: releases
    description:
      - the name of the folder that will hold the releases. This can be relative to C(path) or absolute.
        Returned in the C(deploy_helper.releases_path) fact.

  shared_path:
    required: false
    default: shared
    description:
      - the name of the folder that will hold the shared resources. This can be relative to C(path) or absolute.
        If this is set to an empty string, no shared folder will be created.
        Returned in the C(deploy_helper.shared_path) fact.

  current_path:
    required: false
    default: current
    description:
      - the name of the symlink that is created when the deploy is finalized. Used in C(finalize) and C(clean).
        Returned in the C(deploy_helper.current_path) fact.

  unfinished_filename:
    required: false
    default: DEPLOY_UNFINISHED
    description:
      - the name of the file that indicates a deploy has not finished. All folders in the releases_path that
        contain this file will be deleted on C(state=finalize) with clean=True, or C(state=clean). This file is
        automatically deleted from the I(new_release_path) during C(state=finalize).

  clean:
    required: false
    default: True
    description:
      - Whether to run the clean procedure in case of C(state=finalize).

  keep_releases:
    required: false
    default: 5
    description:
      - the number of old releases to keep when cleaning. Used in C(finalize) and C(clean). Any unfinished builds
        will be deleted first, so only correct releases will count.

notes:
  - Facts are only returned for C(state=query) and C(state=present). If you use both, you should pass any overridden
    parameters to both calls, otherwise the second call will overwrite the facts of the first one.
  - When using C(state=clean), the releases are ordered by I(creation date). You should be able to switch to a
    new naming strategy without problems.
  - Because of the default behaviour of generating the I(new_release) fact, this module will not be idempotent
    unless you pass your own release name with C(release). Due to the nature of deploying software, this should not
    be much of a problem.
'''

EXAMPLES = '''

# Typical usage:
- name: Initialize the deploy root and gather facts
  deploy_helper: path=/path/to/root
- name: Clone the project to the new release folder
  git: repo=git://foosball.example.org/path/to/repo.git dest={{ deploy.new_release_path }} version=v1.1.1"
- name: Add an unfinished file, to allow cleanup on successful finalize
  file: path={{ deploy.new_release_path }}/{{ deploy.unfinished_filename }} state=touch
- name: Perform some build steps, like running your dependency manager for example
  composer: command=install working_dir={{ deploy.new_release_path }}
- name: Finalize the deploy, removing the unfinished file and switching the symlink
  deploy_helper: path=/path/to/root release={{ deploy_helper.new_release }} state=finalize

# Retrieving facts before running a deploy
- name: Run query to gather facts without changing anything
  deploy_helper: path=/path/to/root state=query
  # Remember to set the 'release' parameter when you actually call state=present
- name: Initialize the deploy root
  deploy_helper: path=/path/to/root release={{ deploy_helper.new_release }} state=present

# all paths can be absolute or relative (to the 'path' parameter)
- deploy_helper: path=/path/to/root
                 releases_path=/var/www/project/releases
                 shared_path=/var/www/shared
                 current_path=/var/www/active

# Using your own naming strategy:
- deploy_helper: path=/path/to/root release=v1.1.1 state=present
- deploy_helper: path=/path/to/root release={{ deploy_helper.new_release }} state=finalize

# Using a different unfinished_filename:
- deploy_helper: path=/path/to/root
                 unfinished_filename=README.md
                 release={{ deploy_helper.new_release }}
                 state=finalize

# Postponing the cleanup of older builds:
- deploy_helper: path=/path/to/root release={{ deploy_helper.new_release }} state=finalize clean=False
- deploy_helper: path=/path/to/root state=clean

# Keeping more old releases:
- deploy_helper: path=/path/to/root release={{ deploy_helper.new_release }} state=finalize keep_releases=10
# Or:
- deploy_helper: path=/path/to/root state=clean keep_releases=10

'''

class DeployHelper(object):

    def __init__(self, module):
        module.params['path'] = os.path.expanduser(module.params['path'])

        self.module    = module
        self.file_args = module.load_file_common_arguments(module.params)

        self.clean               = module.params['clean']
        self.current_path        = module.params['current_path']
        self.keep_releases       = module.params['keep_releases']
        self.path                = module.params['path']
        self.release             = module.params['release']
        self.releases_path       = module.params['releases_path']
        self.shared_path         = module.params['shared_path']
        self.state               = module.params['state']
        self.unfinished_filename = module.params['unfinished_filename']

    def gather_facts(self):
        current_path   = os.path.join(self.path, self.current_path)
        releases_path  = os.path.join(self.path, self.releases_path)
        if self.shared_path:
            shared_path    = os.path.join(self.path, self.shared_path)
        else:
            shared_path    = None

        previous_release, previous_release_path = self._get_last_release(current_path)

        if not self.release and (self.state == 'query' or self.state == 'present'):
            self.release = time.strftime("%Y%m%d%H%M%S")

        new_release_path = os.path.join(releases_path, self.release)

        return {
            'project_path':             self.path,
            'current_path':             current_path,
            'releases_path':            releases_path,
            'shared_path':              shared_path,
            'previous_release':         previous_release,
            'previous_release_path':    previous_release_path,
            'new_release':              self.release,
            'new_release_path':         new_release_path,
            'unfinished_filename':      self.unfinished_filename
        }

    def delete_path(self, path):
        if not os.path.lexists(path):
            return False

        if not os.path.isdir(path):
            self.module.fail_json(msg="%s exists but is not a directory" % path)

        if not self.module.check_mode:
            try:
                shutil.rmtree(path, ignore_errors=False)
            except Exception, e:
                self.module.fail_json(msg="rmtree failed: %s" % str(e))

        return True

    def create_path(self, path):
        changed = False

        if not os.path.lexists(path):
            changed = True
            if not self.module.check_mode:
                os.makedirs(path)

        elif not os.path.isdir(path):
            self.module.fail_json(msg="%s exists but is not a directory" % path)

        changed += self.module.set_directory_attributes_if_different(self._get_file_args(path), changed)

        return changed

    def check_link(self, path):
        if os.path.lexists(path):
            if not os.path.islink(path):
                self.module.fail_json(msg="%s exists but is not a symbolic link" % path)

    def create_link(self, source, link_name):
        if not self.module.check_mode:
            if os.path.islink(link_name):
                os.unlink(link_name)
            os.symlink(source, link_name)

        return True

    def remove_unfinished_file(self, new_release_path):
        changed = False
        unfinished_file_path  = os.path.join(new_release_path, self.unfinished_filename)
        if os.path.lexists(unfinished_file_path):
            changed = True
            if not self.module.check_mode:
                os.remove(unfinished_file_path)

        return changed

    def remove_unfinished_builds(self, releases_path):
        changes = 0

        for release in os.listdir(releases_path):
            if (os.path.isfile(os.path.join(releases_path, release, self.unfinished_filename))):
                if self.module.check_mode:
                    changes += 1
                else:
                    changes += self.delete_path(os.path.join(releases_path, release))

        return changes

    def cleanup(self, releases_path):
        changes = 0

        if os.path.lexists(releases_path):
            releases = [ f for f in os.listdir(releases_path) if os.path.isdir(os.path.join(releases_path,f)) ]

            if not self.module.check_mode:
                releases.sort( key=lambda x: os.path.getctime(os.path.join(releases_path,x)), reverse=True)
                for release in releases[self.keep_releases:]:
                    changes += self.delete_path(os.path.join(releases_path, release))
            elif len(releases) > self.keep_releases:
                changes += (len(releases) - self.keep_releases)

        return changes

    def _get_file_args(self, path):
        file_args = self.file_args.copy()
        file_args['path'] = path
        return file_args

    def _get_last_release(self, current_path):
        previous_release = None
        previous_release_path = None

        if os.path.lexists(current_path):
            previous_release_path   = os.path.realpath(current_path)
            previous_release        = os.path.basename(previous_release_path)

        return previous_release, previous_release_path

def main():

    module = AnsibleModule(
        argument_spec = dict(
            path                = dict(aliases=['dest'], required=True, type='str'),
            release             = dict(required=False, type='str', default=''),
            releases_path       = dict(required=False, type='str', default='releases'),
            shared_path         = dict(required=False, type='str', default='shared'),
            current_path        = dict(required=False, type='str', default='current'),
            keep_releases       = dict(required=False, type='int', default=5),
            clean               = dict(required=False, type='bool', default=True),
            unfinished_filename = dict(required=False, type='str', default='DEPLOY_UNFINISHED'),
            state               = dict(required=False, choices=['present', 'absent', 'clean', 'finalize', 'query'], default='present')
        ),
        add_file_common_args = True,
        supports_check_mode  = True
    )

    deploy_helper = DeployHelper(module)
    facts  = deploy_helper.gather_facts()

    result = {
        'state': deploy_helper.state
    }

    changes = 0

    if deploy_helper.state == 'query':
        result['ansible_facts'] = { 'deploy_helper': facts }

    elif deploy_helper.state == 'present':
        deploy_helper.check_link(facts['current_path'])
        changes += deploy_helper.create_path(facts['project_path'])
        changes += deploy_helper.create_path(facts['releases_path'])
        if deploy_helper.shared_path:
            changes += deploy_helper.create_path(facts['shared_path'])

        result['ansible_facts'] = { 'deploy_helper': facts }

    elif deploy_helper.state == 'finalize':
        if not deploy_helper.release:
            module.fail_json(msg="'release' is a required parameter for state=finalize (try the 'deploy_helper.new_release' fact)")
        if deploy_helper.keep_releases <= 0:
            module.fail_json(msg="'keep_releases' should be at least 1")

        changes += deploy_helper.remove_unfinished_file(facts['new_release_path'])
        changes += deploy_helper.create_link(facts['new_release_path'], facts['current_path'])
        if deploy_helper.clean:
            changes += deploy_helper.remove_unfinished_builds(facts['releases_path'])
            changes += deploy_helper.cleanup(facts['releases_path'])

    elif deploy_helper.state == 'clean':
        changes += deploy_helper.remove_unfinished_builds(facts['releases_path'])
        changes += deploy_helper.cleanup(facts['releases_path'])

    elif deploy_helper.state == 'absent':
        # destroy the facts
        result['ansible_facts'] = { 'deploy_helper': [] }
        changes += deploy_helper.delete_path(facts['project_path'])

    if changes > 0:
        result['changed'] = True
    else:
        result['changed'] = False

    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *

main()
