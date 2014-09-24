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


def download(url, headers=None):
    resp = requests.get(url, headers=headers or {})
    if not resp.ok:
        raise Exception("Error downloading '%s': %s" % (url, resp.text))
    return resp.content


def prepare(tgz_b64, location, location_type, cwd, entrypoint, github_token):
    # Extract the decoded tar with ansible.cfg, inventory, keys etc
    tgz = base64.urlsafe_b64decode(tgz_b64)
    tarfile.open(fileobj=StringIO.StringIO(tgz)).extractall()
    for key in os.listdir('id_rsa'):
        os.chmod(os.path.join('id_rsa', key), 0600)
    os.mkdir('playbooks')
    print 'Extracted inventory files and keys, chmods and mkdirs'

    if location_type == 'github':
        print 'Fetch playbook from github repo'
        # location is a repo in the form owner/repo
        url = 'https://api.github.com/repos/%s/tarball' % location
        if github_token:
            headers = {'Authorization': 'token %s' % github_token}
        else:
            headers = {}
        data = download(url, headers)
        print 'Downloaded tarball'
        tarfile.open(fileobj=StringIO.StringIO(data)).extractall('playbooks')
        print 'Extracted tarball'
        tldirs = os.listdir('playbooks')
        if len(tldirs) == 1:
            relpath = os.path.join(cwd, entrypoint) if cwd else entrypoint
            print 'relpath:', relpath
            if not os.path.exists('playbooks/%s' % relpath) \
               and os.path.exists('playbooks/%s/%s' % (tldirs[0], relpath)):
                cwd = os.path.join(tldirs[0], cwd) if cwd else tldirs[0]
                print 'modified cwd:', cwd
    else:  # http file or tarball
        print 'Fetch playbook from http url'
        data = download(location)
        try:
            tf = tarfile.open(fileobj=StringIO.StringIO(data))
            tf.extractall('playbooks')
        except tarfile.TarError:
            entrypoint = 'main.yml'
            cwd = ''
            with open('playbooks/main.yml', 'w') as f:
                f.write(data)
    cwd = os.path.join('playbooks', cwd) if cwd else 'playbooks'
    print 'Cwd:', cwd
    print 'Entrypoint:', entrypoint
    return cwd, entrypoint


def run(cwd, entrypoint, extra_vars):
    args = ['ansible-playbook', entrypoint,
            '-e', str(extra_vars or ''),
            '-e', 'host_key_checking=False',
            '-i', os.path.abspath('inventory')]
    print args
    proc = subprocess.Popen(args, cwd=cwd)
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
    except Exception as exc:
        print 'Error parsing output.json: %r' % exc
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
    cwd = os.getenv('CWD')
    extra_vars = os.getenv('EXTRA_VARS')
    tgz_b64 = os.getenv('TGZ_B64')
    github_token = os.getenv('GITHUB_TOKEN')

    try:
        cwd, entrypoint = prepare(tgz_b64, location, location_type,
                                  cwd, entrypoint, github_token)
    except Exception as exc:
        callback(callback_url, callback_token, False, repr(exc))
        sys.exit(1)

    success, error_msg, ret_dict = run(cwd, entrypoint, extra_vars)

    callback(callback_url, callback_token, success, error_msg, ret_dict)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
