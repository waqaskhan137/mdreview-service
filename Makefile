# Run-command wrappers. Infra (Dockerfiles, compose, watcher, .env) lives under infra/;
# these carry the -f / build context so the canonical commands stay short and correct.
# `docker compose -f infra/docker-compose.yml` sets the project dir to infra/, so infra/.env
# auto-loads (do NOT add --project-directory, which would re-point .env at the cwd).
COMPOSE := docker compose -f infra/docker-compose.yml

# Local run without Docker (stdlib only — no venv, no pip, no build). Override inline, e.g.
#   make run PORT=9000 MDREVIEW_DATA=$HOME/.mdreview
PORT ?= 8137
MDREVIEW_DATA ?= $(CURDIR)/data

.PHONY: build up down watcher smoke run

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

run:      ## run the service locally WITHOUT Docker (PYTHONPATH=src; data in ./data, gitignored)
	PYTHONPATH=src MDREVIEW_DATA=$(MDREVIEW_DATA) PORT=$(PORT) python3 -m mdreview
