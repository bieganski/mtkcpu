#!/bin/bash
#
# Script to build and export Docker image
# Do not invoke directly.
# Rather do: "make build-docker"
#
# @Piotr Styczyński 2021
#

# Image name
VERSION="1.0.0"
IMAGE="mtkcpu:${VERSION}"

echo "Building docker image" && \
docker build --no-cache -t ${IMAGE} . && \
echo "Image was built"
