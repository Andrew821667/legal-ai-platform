.PHONY: lint lint-full test dev prod deploy deploy-macmini integration-test smoke-bots seed backup logs

lint:
	uv run ruff check apps/ packages/ --select F,B904,B905,UP031

lint-full:
	uv run ruff check apps/ packages/
	uv run ruff format --check apps/ packages/

test:
	uv run pytest apps/core-api/tests/ -v

dev:
	docker compose -f infra/compose/docker-compose.dev.yml up --build

seed:
	docker compose -f infra/compose/docker-compose.dev.yml run --rm core-api \
		python -m core_api.cli seed-dev-data

prod:
	docker compose -f infra/compose/docker-compose.prod.yml up -d

deploy:
	./infra/scripts/deploy.sh

deploy-macmini:
	./infra/scripts/deploy_macmini.sh

integration-test:
	./infra/scripts/integration_test.sh

smoke-bots:
	./infra/scripts/smoke_bots_stack.sh

backup:
	./infra/scripts/backup_postgres.sh

logs:
	docker compose -f infra/compose/docker-compose.prod.yml logs -f --tail=50
