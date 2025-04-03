install:
	pip install --upgrade pip && pip install -e ".[dev]"
lint:
	pylint src
format:
	isort . --profile black --multi-line 3 && black .
test:
	python -m pytest tests
