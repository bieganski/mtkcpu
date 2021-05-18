FROM python:3.8.10-buster

LABEL version='{{ version }}'
LABEL org.opencontainers.image.description='{{ readme }}'
LABEL org.opencontainers.image.vendor='{{ author }}'

WORKDIR /toolchain

# Normal update
RUN apt-get update -y

# Install gcc
RUN echo "deb http://deb.debian.org/debian experimental main" >> /etc/apt/sources.list
RUN echo "deb http://ftp.us.debian.org/debian testing main contrib non-free" > /etc/apt/sources.list.d/testing.list
RUN printf "Package: *\nPin: release a=testing\nPin-Priority: 100" > /etc/apt/preferences.d/testing
RUN apt-get update -y
RUN apt-get install -t testing gcc g++ -y -o APT::Immediate-Configure=0

# Install nodejs
RUN apt-get install -y nodejs npm

# Install XPM
RUN npm install --global xpm@latest

# Install gcc extensions
RUN xpm install --global @xpack-dev-tools/riscv-none-embed-gcc@latest

# Install Poetry
RUN pip install poetry

# Install Poetry dependencies
ADD pyproject.toml .
ADD poetry.lock .
RUN poetry install --no-interaction

ADD mtkcpu ./mtkcpu
ADD submodules ./submodules
RUN poetry install --no-interaction

