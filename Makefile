.PHONY: dev setup setup-dogfood test-stack test-graphiti neo4j-shell graph-stats test test-integration lint fmt overlay-install daemon-install daemon-uninstall daemon-logs

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
	pytest tests/ --ignore=tests/test_integration.py

test-integration:
	@echo "Checking server at 127.0.0.1:8080..."
	@curl -sf http://127.0.0.1:8080/health > /dev/null || \
		(echo "\n❌  Server not running. Start with: make dev\n" && exit 1)
	@curl -s http://127.0.0.1:8080/health | python3 -c "\
import json,sys; h=json.load(sys.stdin); m=h.get('memory',{}); \
bad=[k for k,v in m.items() if v not in ('ok', {'status':'disabled'})]; \
print('  stores:', json.dumps(m)); \
[print(f'  ⚠️  {k}: {v}') for k,v in m.items() if v != 'ok']; \
print(f'  skills: {h.get(\"skills_loaded\",0)} loaded')"
	NEUROS_INTEGRATION=1 pytest tests/test_integration.py -v

lint:
	ruff check . && ruff format --check .

fmt:
	ruff format .

overlay-install:
	cp overlay/init.lua ~/dotfiles/mac/.hammerspoon/init.lua
	osascript -e 'tell application "System Events" to tell process "Hammerspoon" to keystroke "r" using {shift down, command down}'
	@echo "Overlay installed and reloaded"

daemon-install:
	mkdir -p ~/Library/Logs/neuros
	cp scripts/launchd/com.neuros.agent.plist ~/Library/LaunchAgents/
	launchctl load -w ~/Library/LaunchAgents/com.neuros.agent.plist
	@echo "NeurOS daemon installed and started"

daemon-uninstall:
	-launchctl unload -w ~/Library/LaunchAgents/com.neuros.agent.plist
	-rm ~/Library/LaunchAgents/com.neuros.agent.plist
	@echo "NeurOS daemon removed"

daemon-logs:
	tail -f ~/Library/Logs/neuros/agent.log
