lint:
	poetry run black .
	poetry run isort .
	poetry run flakehell lint

install:
	bash ./install_toolchain.sh
	poetry install

update:
	poetry update

test:
	poetry run pytest -n 4

