FROM python:3.8.10-buster

LABEL version='{{ version }}'
LABEL org.opencontainers.image.description='{{ readme }}'
LABEL org.opencontainers.image.vendor='{{ author }}'

WORKDIR /toolchain

# Normal update
RUN apt-get update -y

# Install nodejs
RUN apt-get install -y nodejs npm

# Install XPM
RUN npm install --global xpm@latest

# Install gcc extensions
RUN xpm install --global @xpack-dev-tools/riscv-none-embed-gcc@latest
ENV PATH="/root/.local/xPacks/@xpack-dev-tools/riscv-none-embed-gcc/10.2.0-1.2.1/.content/bin:$PATH" 

# Install Poetry
RUN pip install poetry

# Install Poetry dependencies
ADD pyproject.toml .
ADD poetry.lock .
RUN poetry install --no-interaction

ADD mtkcpu ./mtkcpu
ADD submodules ./submodules
RUN poetry install --no-interaction

ENV PATH=$HOME/.poetry/bin/:$PATH
ENTRYPOINT ["poetry", "run", "mtkcpu"]
