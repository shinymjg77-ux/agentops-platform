COMPOSE_FILE=infra/compose/docker-compose.yml

.PHONY: up down logs ps test-e2e test-e2e-phase2 test-e2e-phase3 test-e2e-phase4

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

test-e2e-phase3:
	./scripts/e2e_phase3.sh

test-e2e-phase4:
	./scripts/e2e_phase4.sh
