DOCKER_IMAGE_NAME := docker.io/library/mtkcpu:1.0.0
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

lint:
	poetry run black .
	poetry run isort .
	poetry run flakehell lint

install:
	bash ./install_toolchain.sh
	poetry install

update_local:
	poetry run pip3 install --no-dependencies .

bump_minor:
	poetry run bump2version minor

publish:
	poetry run publish

update:
	poetry update

build:
	poetry build

build-docker:
	bash ./build_docker_image.sh

fetch-gcc: export id := $(shell docker create $(DOCKER_IMAGE_NAME))
fetch-gcc: export temp := $(shell mktemp -p .)
fetch-gcc:
	rm -rf riscv-none-elf-gcc
	docker cp $(id):/root/.local/xPacks/@xpack-dev-tools/riscv-none-elf-gcc/ - > $(temp)
	docker rm -v $(id)
	tar xvf $(temp)
	rm $(temp)
	chmod -R +wx riscv-none-elf-gcc
	@echo "== GCC downloaded from docker to host - run the following command to have it in your PATH:"
	@echo 'export PATH=$$PATH:$(shell realpath riscv-none-elf-gcc/13.2.0-1.2/.content/bin)'
	@echo '======'

test:
	poetry run pytest -n 12
	