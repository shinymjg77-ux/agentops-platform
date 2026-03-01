COMPOSE_FILE=infra/compose/docker-compose.yml

.PHONY: up down logs ps test-e2e test-e2e-phase2

up:
	docker compose -f $(COMPOSE_FILE) up -d --build

down:
	docker compose -f $(COMPOSE_FILE) down

logs:
	docker compose -f $(COMPOSE_FILE) logs -f --tail=100

ps:
	docker compose -f $(COMPOSE_FILE) ps

test-e2e:
	./scripts/e2e_phase1.sh

test-e2e-phase2:
	./scripts/e2e_phase2.sh
