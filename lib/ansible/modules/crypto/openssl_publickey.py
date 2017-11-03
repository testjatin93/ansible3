#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2016, Yanis Guenane <yanis+ansible@guenane.org>
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

ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}


DOCUMENTATION = '''
---
module: openssl_publickey
author: "Yanis Guenane (@Spredzy)"
version_added: "2.3"
short_description: Generate an OpenSSL public key from its private key.
description:
    - "This module allows one to (re)generate OpenSSL public keys from their private keys.
       It uses the pyOpenSSL python library to interact with openssl. Keys are generated
       in PEM format. This module works only if the version of PyOpenSSL is recent enough (> 16.0.0)"
requirements:
    - "python-pyOpenSSL"
options:
    state:
        required: false
        default: "present"
        choices: [ present, absent ]
        description:
            - Whether the public key should exist or not, taking action if the state is different from what is stated.
    force:
        required: false
        default: False
        choices: [ True, False ]
        description:
            - Should the key be regenerated even it it already exists
    path:
        required: true
        description:
            - Name of the file in which the generated TLS/SSL public key will be written.
    privatekey_path:
        required: true
        description:
            - Path to the TLS/SSL private key from which to generate the public key.
'''

EXAMPLES = '''
# Generate an OpenSSL public key.
- openssl_publickey:
    path: /etc/ssl/public/ansible.com.pem
    privatekey_path: /etc/ssl/private/ansible.com.pem

# Force regenerate an OpenSSL public key if it already exists
- openssl_publickey:
    path: /etc/ssl/public/ansible.com.pem
    privatekey_path: /etc/ssl/private/ansible.com.pem
    force: True

# Remove an OpenSSL public key
- openssl_publickey:
    path: /etc/ssl/public/ansible.com.pem
    privatekey_path: /etc/ssl/private/ansible.com.pem
    state: absent
'''

RETURN = '''
privatekey:
    description: Path to the TLS/SSL private key the public key was generated from
    returned: changed or success
    type: string
    sample: /etc/ssl/private/ansible.com.pem
filename:
    description: Path to the generated TLS/SSL public key file
    returned: changed or success
    type: string
    sample: /etc/ssl/public/ansible.com.pem
fingerprint:
    description: The fingerprint of the public key. Fingerprint will be generated for each hashlib.algorithms available.
                 Requires PyOpenSSL >= 16.0 for meaningful output.
    returned: changed or success
    type: dict
    sample:
      md5: "84:75:71:72:8d:04:b5:6c:4d:37:6d:66:83:f5:4c:29"
      sha1: "51:cc:7c:68:5d:eb:41:43:88:7e:1a:ae:c7:f8:24:72:ee:71:f6:10"
      sha224: "b1:19:a6:6c:14:ac:33:1d:ed:18:50:d3:06:5c:b2:32:91:f1:f1:52:8c:cb:d5:75:e9:f5:9b:46"
      sha256: "41:ab:c7:cb:d5:5f:30:60:46:99:ac:d4:00:70:cf:a1:76:4f:24:5d:10:24:57:5d:51:6e:09:97:df:2f:de:c7"
      sha384: "85:39:50:4e:de:d9:19:33:40:70:ae:10:ab:59:24:19:51:c3:a2:e4:0b:1c:b1:6e:dd:b3:0c:d9:9e:6a:46:af:da:18:f8:ef:ae:2e:c0:9a:75:2c:9b:b3:0f:3a:5f:3d"
      sha512: "fd:ed:5e:39:48:5f:9f:fe:7f:25:06:3f:79:08:cd:ee:a5:e7:b3:3d:13:82:87:1f:84:e1:f5:c7:28:77:53:94:86:56:38:69:f0:d9:35:22:01:1e:a6:60:...:0f:9b"
'''

import errno
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.crypto import get_fingerprint
from ansible.module_utils.pycompat24 import get_exception

try:
    from OpenSSL import crypto
except ImportError:
    pyopenssl_found = False
else:
    pyopenssl_found = True

import os
from ansible.module_utils._text import to_native


class PublicKeyError(Exception):
    pass


class PublicKey(object):

    def __init__(self, module):
        self.state = module.params['state']
        self.force = module.params['force']
        self.name = os.path.basename(module.params['path'])
        self.path = module.params['path']
        self.privatekey_path = module.params['privatekey_path']
        self.privatekey = None
        self.changed = True
        self.fingerprint = {}
        self.check_mode = module.check_mode


    def generate(self, module):
        """Generate the public key."""

        if not os.path.exists(self.path) or self.force:
            try:
                privatekey_content = open(self.privatekey_path, 'r').read()
                self.privatekey = crypto.load_privatekey(crypto.FILETYPE_PEM, privatekey_content)
                publickey_content = crypto.dump_publickey(crypto.FILETYPE_PEM, self.privatekey)
                publickey_file = open(self.path, 'w')
                publickey_file.write(publickey_content)
                publickey_file.close()
            except (IOError, OSError) as exc:
                raise PublicKeyError(exc)
            except AttributeError as exc:
                self.remove()
                raise PublicKeyError('You need to have PyOpenSSL>=16.0.0 to generate public keys')
        else:
            self.changed = False

        file_args = module.load_file_common_arguments(module.params)
        self.fingerprint = get_fingerprint(self.privatekey_path)
        if module.set_fs_attributes_if_different(file_args, False):
            self.changed = True

    def remove(self):
        """Remove the public key from the filesystem."""

        try:
            os.remove(self.path)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise PublicKeyError(exc)
            else:
                self.changed = False

    def dump(self):
        """Serialize the object into a dictionary."""

        result = {
            'privatekey': self.privatekey_path,
            'filename': self.path,
            'changed': self.changed,
            'fingerprint': self.fingerprint,
        }

        return result


def main():

    module = AnsibleModule(
        argument_spec = dict(
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            force=dict(default=False, type='bool'),
            path=dict(required=True, type='path'),
            privatekey_path=dict(type='path'),
        ),
        supports_check_mode = True,
        add_file_common_args = True,
    )

    if not pyopenssl_found:
        module.fail_json(msg='the python pyOpenSSL module is required')

    path = module.params['path']
    privatekey_path = module.params['privatekey_path']
    base_dir = os.path.dirname(module.params['path'])

    if not os.path.isdir(base_dir):
        module.fail_json(name=base_dir, msg='The directory %s does not exist or the file is not a directory' % base_dir)

    public_key = PublicKey(module)
    if public_key.state == 'present':

        # This is only applicable when generating a new public key.
        # When removing one the privatekey_path should not be required.
        if not privatekey_path:
            module.fail_json(msg='When generating a new public key you must specify a private key')

        if not os.path.exists(privatekey_path):
            module.fail_json(name=privatekey_path, msg='The private key %s does not exist' % privatekey_path)

        if module.check_mode:
            result = public_key.dump()
            result['changed'] = module.params['force'] or not os.path.exists(path)
            module.exit_json(**result)

        try:
            public_key.generate(module)
        except PublicKeyError as exc:
            module.fail_json(msg=to_native(exc))
    else:

        if module.check_mode:
            result = public_key.dump()
            result['changed'] = os.path.exists(path)
            module.exit_json(**result)

        try:
            public_key.remove()
        except PublicKeyError as exc:
            module.fail_json(msg=to_native(exc))

    result = public_key.dump()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
