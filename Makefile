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

test-docker:
	docker run docker.io/library/mtkcpu:1.0.0 tests cpu

test:
	poetry run pytest -n 4

