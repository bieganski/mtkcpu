from bieganski/riscv-fpga:tagname

# Install Poetry
RUN pip3 install --upgrade pip
RUN pip3 install poetry
ADD pyproject.toml .
ADD poetry.lock .

# Install mtkcpu.
ADD mtkcpu ./mtkcpu
RUN poetry install --no-interaction
ENV PATH=$HOME/.poetry/bin/:$PATH

# For openOCD co-simulation.
RUN apt-get install lsof