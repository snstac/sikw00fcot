# Dockerfile for sikw00fcot — SiKW00F Drone Telemetry to TAK Gateway.
#
# Copyright Sensors & Signals LLC https://www.snstac.com
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#

# Download base image ubuntu 22.04
FROM ubuntu:22.04

# LABEL about the custom image
LABEL description="SiKW00F Drone Telemetry to TAK Gateway."

# Disable Prompt During Packages Installation
ARG DEBIAN_FRONTEND=noninteractive

# Update Ubuntu Software repository
RUN apt update
RUN apt upgrade -y
RUN apt install -y python3
RUN apt install -y python3-pip
RUN apt install -y python3-cryptography

# Build sikw00fcot (with wss:// / takproto support)
COPY . /sikw00fcot/
RUN cd /sikw00fcot/ && python3 -m pip install '.[with_takproto]'
RUN rm -R /sikw00fcot/

# Copy sikw00fcot configuration
RUN mkdir /etc/sikw00fcot/
COPY docker/sikw00fcot-docker-example.conf /etc/default/sikw00fcot

# Copy start.sh script and define default command for the container
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh
CMD ["/start.sh"]
