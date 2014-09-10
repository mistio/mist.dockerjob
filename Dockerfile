FROM dockerfile/ansible
MAINTAINER Mist Inc <support@mist.io>
RUN pip install mist.client
RUN pip install mist.ansible
