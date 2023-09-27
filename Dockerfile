FROM ubuntu:22.04

LABEL version='{{ version }}'
LABEL org.opencontainers.image.description='{{ readme }}'
LABEL org.opencontainers.image.vendor='{{ author }}'

SHELL ["/bin/bash", "-c"]
WORKDIR /toolchain

# Normal update
RUN apt-get update -y

RUN apt-get -y install curl git pip

# Install proper nodejs version.
ENV NVM_DIR=/toolchain
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh > install.sh
RUN echo "69da4f89f430cd5d6e591c2ccfa2e9e3ad55564ba60f651f00da85e04010c640  install.sh" > checksum.txt
RUN sha256sum -c checksum.txt
RUN bash ./install.sh
RUN source "$NVM_DIR/nvm.sh" && nvm install v16.20.0 && nvm use v16.20.0

# Install XPM
RUN source "$NVM_DIR/nvm.sh" && npm install --global xpm@0.16.4

# Install gcc toolchain
RUN source "$NVM_DIR/nvm.sh" && xpm install --global @xpack-dev-tools/riscv-none-elf-gcc@13.2.0-1.2 --verbose
ENV PATH="/root/.local/xPacks/@xpack-dev-tools/riscv-none-elf-gcc/13.2.0-1.2/.content/bin:$PATH"


RUN pip3 install --upgrade pip
RUN pip3 install poetry

# Install Poetry dependencies
ADD pyproject.toml .
ADD poetry.lock .

RUN poetry install --no-interaction

ADD mtkcpu ./mtkcpu
RUN poetry install --no-interaction

ENV PATH=$HOME/.poetry/bin/:$PATH
