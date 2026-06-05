.PHONY: dev setup test-stack test lint fmt overlay-install

dev:
	uvicorn neuros.main:app --reload --host 0.0.0.0 --port 8000

setup:
	python scripts/setup_db.py

test-stack:
	python scripts/test_inference.py
	python scripts/test_embed.py
	python scripts/test_memory.py

test:
	pytest tests/

lint:
	ruff check . && ruff format --check .

fmt:
	ruff format .

overlay-install:
	cp overlay/init.lua ~/.hammerspoon/init.lua
	@echo "Reload Hammerspoon: CMD+SHIFT+R"
