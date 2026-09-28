.PHONY: up down logs test lint format clean
up:
	docker compose up --build
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
test:
	pytest
lint:
	python -m compileall -q src
format:
	python -m compileall -q src
clean:
	docker compose down -v
