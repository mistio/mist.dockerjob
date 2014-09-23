#!/usr/bin/env python

import os
import sys
import json
import base64
import tarfile
import StringIO
from time import sleep
from subprocess import Popen
from threading import Timer

import requests

MAX_SIZE = 1024 * 1024 * 100


def chmod_keys():
    # chmod keys in id_rsa dir
    keys = os.listdir('id_rsa')
    for key in keys:
        os.chmod(os.path.join("id_rsa", key), 0600)


def extract(content, path="."):
    f = StringIO.StringIO(content)
    tf = tarfile.open(fileobj=f)
    tf.extractall(path=path)


def download_file(url, max_size=MAX_SIZE):
    # NOTE the stream=True parameter
    resp = requests.get(url)
    return resp.content


def command(args, timeout):
    proc = Popen(args)

    kill_proc = lambda p: p.kill()

    timer = Timer(timeout, kill_proc, [proc])
    timer.start()
    returncode = proc.wait()
    timer.cancel()

    return returncode


def parse_output(output_path="/tmp/output.json"):
    """
    If /tmp/output.json exists, try to load it and return the ret_dict, else
    return {}
    """
    ret_dict = {}
    if os.path.isfile(output_path):
        with open(output_path, "r") as f:
            output_content = f.read()
    else:
        return ret_dict

    # In case the file is empty, the json.loads will break with ValueError
    try:
        ret_dict = json.loads(output_content)
        return ret_dict
    except ValueError:
        return ret_dict


def main():
    url = os.getenv('URL')
    entrypoint = os.getenv('ENTRYPOINT')
    extra_vars = os.getenv('EXTRA_VARS')
    tgz_b64 = os.getenv('TGZ_B64')
    callback = os.getenv('CALLBACK_URL')
    token = os.getenv('TOKEN')

    try:
        # Decode base64
        decoded = base64.urlsafe_b64decode(tgz_b64)

        # Extract the decoded tar with ansible.cfg, inventory, keys etc
        extract(decoded)
        chmod_keys()

        # Download content from url and mkdir playbooks
        downloaded_content = download_file(url)
        os.mkdir("playbooks")
        try:
            extract(downloaded_content, "playbooks")
        except tarfile.TarError:
            entrypoint = 'main.yml'
            with open("playbooks/main.yml", "w") as f:
                f.write(downloaded_content)
    except Exception as exc:
        payload = {
            'success': False,
            'error_msg': repr(exc),
            'token': token
        }

        requests.post(callback, data=json.dumps(payload), verify=False)

    args = ['ansible-playbook', 'playbooks/' + entrypoint, '-e', '"%s"' % extra_vars]
    returncode = command(args, 60*30)

    if returncode == 0:
        success = True
        error_msg = None
    else:
        success = False
        error_msg = "Running command exited with return code %d" % returncode

    ret_dict = parse_output()

    payload = {
        'success': success,
        'error_msg': error_msg,
        'token': token,
        'ret_dict': ret_dict
    }

    for i in range(0, 5):
        try:
            requests.post(callback, data=json.dumps(payload), verify=False)
            # Exit with returncode of command. 0 if success.
            sys.exit(returncode)
        except:
            sleep(4)

    sys.exit(returncode)

if __name__ == "__main__":
    main()