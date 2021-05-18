lint:
	poetry run black .
	poetry run isort .
	poetry run flakehell lint

install:
	bash ./install_toolchain.sh
	poetry install

bump_minor:
	poetry run bump2version minor

publish:
	poetry run publish

update:
	poetry update

test:
	poetry run pytest -n 4

