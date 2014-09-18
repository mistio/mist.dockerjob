FROM dockerfile/ansible
MAINTAINER Mist Inc <support@mist.io>
RUN pip install mist.client requests
RUN pip install mist.ansible

RUN mkdir -p /tmp/mist
ADD scripts/mist.py /tmp/mist

WORKDIR /tmp/mist
ENTRYPOINT run.py