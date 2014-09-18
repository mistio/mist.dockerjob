#!/usr/bin/env python

import os
import sys
import base64
import tarfile
import StringIO
from subprocess import Popen, PIPE
from threading import Timer

import requests

MAX_SIZE = 1024 * 1024 * 100


def chmod_keys():
    # chmod keys in id_rsa dir
    keys = os.listdir('id_rsa')
    for key in keys:
        os.chmod(os.path.join("id_rsa", key), 600)


def extract(content, path="."):
    f = StringIO.StringIO(content)
    tf = tarfile.open(fileobj=f)
    tf.extractall(path=path)


def download_file(url, max_size=MAX_SIZE):
    # NOTE the stream=True parameter
    resp = requests.get(url, stream=True)
    size = int(resp.headers['content-length'])
    print "Request size: %d" % size
    if max_size and size > max_size:
        raise Exception('Size is %d > %d' % (size, max_size))
    return resp.content


def command(args, timeout):
    proc = Popen(args, stdout=PIPE, stderr=PIPE)

    kill_proc = lambda p: p.kill()

    timer = Timer(timeout, kill_proc, [proc])
    timer.start()
    stdout, stderr = proc.communicate()
    returncode = proc.returncode
    timer.cancel()

    return stdout, stderr, returncode


def main():
    url = os.getenv('URL')
    entrypoint = os.getenv('ENTRYPOINT')
    extra_vars = os.getenv('EXTRA_VARS')
    tgz_b64 = os.getenv('TGZ_B64')

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
        with open("playbooks/main.yml" + "w") as f:
            f.write(downloaded_content)

    args = ['ansible-playbook', 'playbooks/' + entrypoint, '-e', '"%s"' % extra_vars]

    stdout, stderr, returncode = command(args, 60*30)

    if returncode == 0:
        print "Everything went ok"
        print stdout
        sys.exit(0)
    else:
        print "Skata, skata stin 5-6-7"
        print stderr
        sys.exit(1)

if __name__ == "__main__":
    main()