# Run-command wrappers. Infra (Dockerfiles, compose, watcher, .env) lives under infra/;
# these carry the -f / build context so the canonical commands stay short and correct.
# `docker compose -f infra/docker-compose.yml` sets the project dir to infra/, so infra/.env
# auto-loads (do NOT add --project-directory, which would re-point .env at the cwd).
COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: build up down watcher smoke

build:    ## build the service image from the repo-root context
	docker build -f infra/Dockerfile -t mdreview-service .

up:       ## build + run the service on localhost:8137
	$(COMPOSE) up -d --build

down:     ## stop the service
	$(COMPOSE) down

watcher:  ## run service + the opt-in watcher (needs a token in infra/.env)
	$(COMPOSE) --profile watcher up -d --build

smoke:    ## healthcheck the running service
	curl -fsS localhost:8137/healthz && echo
