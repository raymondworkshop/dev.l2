# Echo — common commands
# Usage: make <target>

ROOT     := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PYTHON   := $(ROOT)/.venv/bin/python
PIP      := $(ROOT)/.venv/bin/pip
FLASK_HOST ?= 0.0.0.0
FLASK_PORT ?= 5050

PLIST_SRC  := $(ROOT)/deploy/com.beanworkshop.echo.plist
PLIST_ID   := com.beanworkshop.echo
PLIST_DEST := $(HOME)/Library/LaunchAgents/$(PLIST_ID).plist
UI_DOMAIN  := gui/$$(id -u)

.PHONY: help setup install install-web env build run api web start synthesize clean-pyc \
	service-install service-uninstall service-start service-stop service-restart service-status service-logs

help:
	@echo "Echo Makefile"
	@echo ""
	@echo "  make setup              First-time: venv + deps + .env + build UI"
	@echo "  make install / install-web / env / build"
	@echo "  make run                Foreground API+UI on :$(FLASK_PORT)"
	@echo "  make start              build then run (foreground)"
	@echo "  make web                Vite hot-reload :5173"
	@echo "  make synthesize         Neural US TTS (SOURCE=id)"
	@echo ""
	@echo "  Default background service (login + KeepAlive):"
	@echo "  make service-install    Install + start LaunchAgent (do once)"
	@echo "  make service-status     Is it running?"
	@echo "  make service-restart    Rebuild UI + restart service"
	@echo "  make service-stop / service-start / service-uninstall"
	@echo "  make service-logs       Tail service logs"
	@echo ""
	@echo "Open http://127.0.0.1:$(FLASK_PORT)"

setup: env
	@test -d $(ROOT)/.venv || python3 -m venv $(ROOT)/.venv
	$(PIP) install -r $(ROOT)/server/requirements.txt
	$(MAKE) install-web
	$(MAKE) build
	@echo "Done. Enable always-on: make service-install"
	@echo "Or one-shot: make run"

install:
	@test -d $(ROOT)/.venv || python3 -m venv $(ROOT)/.venv
	$(PIP) install -r $(ROOT)/server/requirements.txt

install-web:
	npm --prefix $(ROOT)/web install

env:
	@if [ ! -f $(ROOT)/.env ]; then cp $(ROOT)/.env.example $(ROOT)/.env && echo "Created .env"; else echo ".env already exists"; fi

build:
	npm --prefix $(ROOT)/web run build

run api:
	FLASK_HOST=$(FLASK_HOST) FLASK_PORT=$(FLASK_PORT) $(PYTHON) $(ROOT)/server/app.py

start: build run

web:
	npm --prefix $(ROOT)/web run dev -- --host 127.0.0.1 --port 5173

SOURCE ?= fixture-npr-climate
synthesize:
	$(PYTHON) $(ROOT)/server/synthesize.py $(SOURCE)

clean-pyc:
	find $(ROOT) -type d -name __pycache__ -not -path '$(ROOT)/.venv/*' -exec rm -rf {} + 2>/dev/null || true
	find $(ROOT) -name '*.pyc' -not -path '$(ROOT)/.venv/*' -delete 2>/dev/null || true

# --- LaunchAgent (default always-on service) ---

service-install: build
	@chmod +x $(ROOT)/scripts/echo-serve.sh
	@mkdir -p $(HOME)/Library/LaunchAgents $(ROOT)/data
	@sed 's|__ECHO_ROOT__|$(ROOT)|g' $(PLIST_SRC) > $(PLIST_DEST)
	@-lsof -tiTCP:$(FLASK_PORT) -sTCP:LISTEN | xargs kill 2>/dev/null || true
	@sleep 0.4
	@launchctl bootout $(UI_DOMAIN)/$(PLIST_ID) 2>/dev/null || true
	@launchctl bootstrap $(UI_DOMAIN) $(PLIST_DEST)
	@launchctl enable $(UI_DOMAIN)/$(PLIST_ID)
	@launchctl kickstart -k $(UI_DOMAIN)/$(PLIST_ID)
	@sleep 0.8
	@$(MAKE) service-status
	@echo "Installed. Echo starts on login and stays up (KeepAlive)."

service-uninstall:
	@launchctl bootout $(UI_DOMAIN)/$(PLIST_ID) 2>/dev/null || true
	@rm -f $(PLIST_DEST)
	@echo "Removed LaunchAgent $(PLIST_ID)"

service-start:
	@test -f $(PLIST_DEST) || (echo "Not installed. Run: make service-install" && exit 1)
	@launchctl bootstrap $(UI_DOMAIN) $(PLIST_DEST) 2>/dev/null || true
	@launchctl kickstart -k $(UI_DOMAIN)/$(PLIST_ID)

service-stop:
	@launchctl bootout $(UI_DOMAIN)/$(PLIST_ID) 2>/dev/null || true
	@echo "Stopped. Start again: make service-start"

service-restart: build
	@chmod +x $(ROOT)/scripts/echo-serve.sh
	@-lsof -tiTCP:$(FLASK_PORT) -sTCP:LISTEN | xargs kill 2>/dev/null || true
	@sleep 0.3
	@launchctl kickstart -k $(UI_DOMAIN)/$(PLIST_ID) 2>/dev/null || \
		(test -f $(PLIST_DEST) && launchctl bootstrap $(UI_DOMAIN) $(PLIST_DEST) && launchctl kickstart -k $(UI_DOMAIN)/$(PLIST_ID))
	@sleep 0.5
	@$(MAKE) service-status

service-status:
	@echo "plist: $(PLIST_DEST)"
	@if [ -f $(PLIST_DEST) ]; then echo "installed: yes"; else echo "installed: no (make service-install)"; fi
	@launchctl print $(UI_DOMAIN)/$(PLIST_ID) 2>/dev/null | egrep 'state =|pid =|path =|last exit' || echo "LaunchAgent not loaded"
	@curl -s -o /dev/null -w "http://127.0.0.1:$(FLASK_PORT)/api/health → %{http_code}\n" http://127.0.0.1:$(FLASK_PORT)/api/health || echo "not reachable"

service-logs:
	@echo "--- stdout (data/echo-service.log) ---"
	@tail -n 40 $(ROOT)/data/echo-service.log 2>/dev/null || echo "(empty)"
	@echo "--- stderr (data/echo-service.err.log) ---"
	@tail -n 40 $(ROOT)/data/echo-service.err.log 2>/dev/null || echo "(empty)"
