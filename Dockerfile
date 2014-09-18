FROM dockerfile/ansible
MAINTAINER Mist Inc <support@mist.io>
RUN pip install mist.client requests boto
RUN pip install mist.ansible

RUN mkdir -p /tmp/mist
ADD scripts/run.py /tmp/mist/run.py

WORKDIR /tmp/mist/
ENTRYPOINT python run.py