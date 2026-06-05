.PHONY: dev setup setup-dogfood test-stack test-graphiti neo4j-shell graph-stats test lint fmt overlay-install

dev:
	uvicorn neuros.main:app --reload --host 127.0.0.1 --port 8080

setup:
	python scripts/setup_db.py

setup-dogfood:
	python scripts/setup_dogfood.py

test-stack:
	python scripts/test_inference.py
	python scripts/test_embed.py
	python scripts/test_memory.py
	python scripts/test_graphiti.py

test-graphiti:
	python scripts/test_graphiti.py

neo4j-shell:
	docker exec -it neo4j cypher-shell -u neo4j -p neuros_neo4j_pass

graph-stats:
	python -c "\
import asyncio; \
from neuros.memory.graphiti_store import GraphitiStore; \
from neuros.config import settings; \
s = settings; \
async def main(): \
    g = GraphitiStore(s.neo4j_uri, s.neo4j_user, s.neo4j_password, s.lts1_base_url, s.model_fast, embed_base_url=s.lts1_embed_url); \
    h = await g.health(); \
    print(h); \
asyncio.run(main())"

test:
	pytest tests/

lint:
	ruff check . && ruff format --check .

fmt:
	ruff format .

overlay-install:
	cp overlay/init.lua ~/.hammerspoon/init.lua
	@echo "Reload Hammerspoon: CMD+SHIFT+R"
