.PHONY: lint lint-fix test test-coverage

lint:
	uv run ruff check .
	uv run ruff format --check .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

test-cov:
	uv run coverage run -m pytest -q && uv run coverage report --fail-under=90
