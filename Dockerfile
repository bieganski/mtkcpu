FROM python:3.10

LABEL version='{{ version }}'
LABEL org.opencontainers.image.description='{{ readme }}'
LABEL org.opencontainers.image.vendor='{{ author }}'

WORKDIR /toolchain

# Normal update
RUN apt-get update -y

# Install nodejs
RUN curl -sL https://deb.nodesource.com/setup_16.x  | bash -
RUN apt-get -y install nodejs

# Install XPM
RUN npm install --global xpm@latest

# Install gcc extensions
RUN xpm install --global @xpack-dev-tools/riscv-none-elf-gcc@latest --verbose
ENV PATH="/root/.local/xPacks/@xpack-dev-tools/riscv-none-embed-gcc/12.2.0-1.3.1/.content/bin:$PATH" 

# Install Poetry
RUN pip install poetry

# Install Poetry dependencies
ADD pyproject.toml .
ADD poetry.lock .
RUN poetry install --no-interaction

ADD mtkcpu ./mtkcpu
RUN poetry install --no-interaction

ENV PATH=$HOME/.poetry/bin/:$PATH
ENTRYPOINT ["poetry", "run", "mtkcpu"]
