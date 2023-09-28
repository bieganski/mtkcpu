FROM ubuntu:22.04

LABEL version='{{ version }}'
LABEL org.opencontainers.image.description='{{ readme }}'
LABEL org.opencontainers.image.vendor='{{ author }}'

SHELL ["/bin/bash", "-c"]
ENV WORKDIR=/toolchain
WORKDIR /toolchain

ARG DEBIAN_FRONTEND=noninteractive

# Normal update
RUN apt-get update -y

RUN apt-get -y install curl git pip file cmake

ENV NVM_SH=/root/.nvm/nvm.sh
# Install nvm, node and xpm.
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh > install.sh
RUN echo "69da4f89f430cd5d6e591c2ccfa2e9e3ad55564ba60f651f00da85e04010c640  install.sh" > checksum.txt
RUN sha256sum -c checksum.txt
RUN bash ./install.sh
RUN source $NVM_SH
RUN source $NVM_SH && nvm install v16.20.0 && nvm use v16.20.0
RUN source $NVM_SH && npm install --global xpm@0.16.4

# Install gcc toolchain
RUN source $NVM_SH && xpm install --global @xpack-dev-tools/riscv-none-elf-gcc@13.2.0-1.2 --verbose
ENV PATH="/root/.local/xPacks/@xpack-dev-tools/riscv-none-elf-gcc/13.2.0-1.2/.content/bin:$PATH"

RUN pip3 install --upgrade pip
RUN pip3 install poetry

# Install Poetry dependencies
ADD pyproject.toml .
ADD poetry.lock .

# Install mtkcpu.
# RUN poetry install --no-interaction
ADD mtkcpu ./mtkcpu
RUN poetry install --no-interaction

ENV PATH=$HOME/.poetry/bin/:$PATH

# Install 'iceprog' dependencies.
RUN apt-get install -y libftdi-dev

# Install 'yosys' dependencies.
RUN apt-get install -y build-essential clang bison flex \
	libreadline-dev gawk tcl-dev libffi-dev git \
	graphviz xdot pkg-config python3 libboost-system-dev \
	libboost-python-dev libboost-filesystem-dev zlib1g-dev

# Install 'nextpnr' dependencies.
RUN apt-get install -y libboost-all-dev libeigen3-dev

# By default yosys and iceprog are installed in /usr/local/bin/, and for nextpnr we specify it explicitly.

RUN git clone https://github.com/YosysHQ/icestorm && cd icestorm && make -j15 && make install
RUN git clone https://github.com/YosysHQ/yosys && cd yosys && make -j15 && make install
RUN git clone https://github.com/YosysHQ/nextpnr && cd nextpnr && cmake . -DARCH=ice40 -DICESTORM_INSTALL_PREFIX=/usr/local/ && make -j15 && make install

# Make sure all synthesis binaries are in PATH.
RUN which iceprog yosys nextpnr-ice40 
