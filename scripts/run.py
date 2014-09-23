#!/usr/bin/env python

import os
import sys
import time
import json
import base64
import tarfile
import StringIO
import threading
import subprocess

import requests


def prepare(tgz_b64, location, location_type, entrypoint, github_token=''):
    # Extract the decoded tar with ansible.cfg, inventory, keys etc
    tgz = base64.urlsafe_b64decode(tgz_b64)
    tarfile.open(fileobj=StringIO.StringIO(tgz)).extractall()
    untar(base64.urlsafe_b64decode(tgz_b64))
    for key in os.listdir('id_rsa'):
        os.chmod(os.path.join("id_rsa", key), 0600)

    headers = {}
    url = location
    if location_type == 'github':
        # location is a repo in the form owner/repo
        url = 'https://api.github.com/repos/%s/tarball/master' % location
        if github_token:
            headers = {'Authorization': 'token %s' % github_token}

    # Download content from url and mkdir playbooks
    data = requests.get(url, headers=headers).content

    os.mkdir("playbooks")
    try:
        tarfile.open(fileobj=StringIO.StringIO(data)).extractall('playbooks')
    except tarfile.TarError:
        entrypoint = 'main.yml'
        with open("playbooks/main.yml", "w") as f:
            f.write(data)
    return entrypoint


def run(entrypoint, extra_vars):
    args = ['ansible-playbook',
            'playbooks/' + entrypoint,
            '-e',
            '"%s"' % extra_vars]

    proc = subprocess.Popen(args)
    timer = threading.Timer(60 * 30, proc.kill)
    timer.start()
    returncode = proc.wait()
    timer.cancel()

    if returncode == 0:
        success = True
        error_msg = None
    else:
        success = False
        error_msg = "Running command exited with return code %d" % returncode
    try:
        with open('/tmp/output.json') as f:
            ret_dict = json.load(f)
    except:
        ret_dict = {}
    return success, error_msg, ret_dict


def callback(url, token, success, error_msg='', ret_dict=None):
    data = json.dumps({
        'success': success,
        'error_msg': error_msg,
        'ret_dict': ret_dict or {},
        'token': token,
    })
    for i in range(5):
        try:
            if requests.post(url, data=data, verify=False).ok:
                return True
        except:
            pass
        time.sleep(5)
    return False


def main():
    callback_url = os.getenv('CALLBACK_URL')
    callback_token = os.getenv('CALLBACK_TOKEN')
    location = os.getenv('LOCATION')
    location_type = os.getenv('LOCATION_TYPE')
    entrypoint = os.getenv('ENTRYPOINT')
    extra_vars = os.getenv('EXTRA_VARS')
    tgz_b64 = os.getenv('TGZ_B64')
    github_token = os.getenv('GITHUB_TOKEN')

    try:
        entrypoint = prepare(tgz_b64, location, location_type,
                             entrypoint, github_token)
    except Exception as exc:
        callback(callback_url, callback_token, False, repr(exc))
        sys.exit(1)

    success, error_msg, ret_dict = run(entrypoint, extra_vars)

    callback(callback_url, callback_token, success, error_msg, ret_dict)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
