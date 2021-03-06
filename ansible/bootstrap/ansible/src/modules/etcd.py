#!/usr/bin/env python
# NOTE: sourced from https://github.com/modcloth-labs/ansible-module-etcd
# -*- coding: utf-8 -*-
from ansible.module_utils.basic import *

DOCUMENTATION = """
---
module: etcd
short_description: Set and delete values from etcd
description:
  - Sets or deletes values in etcd.
  - Parent directories of the key will be created if they do not already exist.
version_added: "0.1"
author: Rafe Colton
notes:
  - Supports check mode.
  - Adapted from https://github.com/devo-ps/ansible-addons
requirements:
  - requests >= 2.8.1
  - python-etcd >= 0.4.2
options:
  state:
    description:
      - This will be the state of the key in etcd
      - after this module completes its operations.
    required: true
    choices: [present, absent]
    default: null
  host:
    description:
      - The etcd host to use
    required: false
    default: 127.0.0.1
  port:
    description:
      - The port to use on the above etcd host
    required: false
    default: 4001
  key:
    description:
      - The key in etcd at which to set the value
    required: true
    default: null
  value:
    description:
      - The value to be set in etcd
    required: true
    default: null
  allow_redirect:
    description:
      - Etcd attempts to redirect all write requests to the etcd master
      - for safety reasons. If allow_redirect is set to false, such
      - redirection will not be allowed. In this case, the value for `host`
      - must be the etcd leader or this module will err.
    required: false
    default: true
"""

EXAMPLES = """
# set a value in etcd
- etcd:
    state=present
    host=my-etcd-host.example.com
    port=4001
    key=/asdf/foo/bar/baz/gorp
    value=my-foo-bar-baz-gor-server.prod.example.com

# delete a value from etcd
- etcd:
    state=absent
    host=my-etcd-host.example.com
    port=4001
    key=/asdf/foo/bar/baz/gorp

# NOTE: you may wish to use `connection: local` with these tasks
"""

try:
    import etcd
    etcd_found = True
except ImportError:
    etcd_found = False

try:
    import requests
    requests_found = True
except ImportError:
    requests_found = False


def main():
    stack = []

    module = AnsibleModule(
        argument_spec=dict(
            state=dict(required=True, choices=['present', 'absent']),
            allow_redirect=dict(required=False, default=True),
            host=dict(required=False, default='127.0.0.1'),
            key=dict(required=True),
            port=dict(default=4001),
            value=dict(required=False, default=None),
        ),
        supports_check_mode=True
    )

    if not etcd_found:
        module.fail_json(msg="the python etcd module is required")

    if not requests_found:
        module.fail_json(msg="the python requests module is required")

    state = module.params['state']
    target_host = module.params['host']
    target_port = int(module.params['port'])

    key = module.params['key']
    value = module.params['value']

    if state == 'present' and not value:
        module.fail_json(msg='Value is required with state="present".')

    kwargs = {
        'host': target_host,
        'port': target_port,
        'allow_redirect': module.params['allow_redirect']
    }

    client = etcd.Client(**kwargs)

    change = False
    prev_value = None

    # attempt to get key
    try:
        prev_value = client.get(key).value
    except requests.ConnectionError:
        module.fail_json(msg="Can not connect to target.")
    except etcd.EtcdKeyNotFound:
        prev_value = None
    except etcd.EtcdException as err:
        module.fail_json(msg="Etcd error: %s" % err)

    # handle check mode
    if module.check_mode:
        if ((state == 'absent' and prev_value is not None) or
                (state == 'present' and prev_value != value)):
                    change = True
        module.exit_json(changed=change)

    if state == 'present':
        stack = []
        dirname = os.path.dirname(key)

        while True:
            if dirname == "/":
                break
            else:
                stack.append(dirname)
            dirname = os.path.dirname(dirname)

        # ensure parent directories exist (like mkdir -p)
        while stack:
            d = stack.pop()
            try:
                client.get(d).value
            except requests.ConnectionError:
                module.fail_json(msg="Can not connect to target.")
            except KeyError:
                client.write(d, '', dir=True)
                prev_value = None
            except etcd.EtcdException as err:
                module.fail_json(msg="Etcd error: %s" % err)

        try:
            set_res = client.write(key, value)
            if set_res.newKey or prev_value != value:
                change = True
        except requests.ConnectionError:
            module.fail_json(msg="Can not connect to target.")
    elif state == 'absent':
        if prev_value is not None:
            change = True
            try:
                set_res = client.delete(key)
            except requests.ConnectionError:
                module.fail_json(msg="Can not connect to target.")

    results = {
        'changed': change,
        'value': value,
        'key': key
    }

    if prev_value != value:
        results['prev_value'] = prev_value

    module.exit_json(**results)

main()
