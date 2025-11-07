.PHONY: up down logs dev install test clean

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f

dev:
	uvicorn semantix.main:app --reload --port 8080

install:
	pip install -e .

test:
	pytest

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +

