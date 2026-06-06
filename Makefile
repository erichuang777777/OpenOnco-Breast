# OpenOnco — local development helper
# Usage:
#   make dev        start backend (:8000) + frontend dev server (:5173) together
#   make install    install all dependencies (first-time setup)
#   make backend    backend only
#   make frontend   frontend only
#   make test       run all tests
#   make build      build the production frontend bundle

.PHONY: dev install backend frontend test build

# ── First-time setup ──────────────────────────────────────────────────────────
install:
	@[ -f .env ] && echo ".env already exists, skipping copy" || (cp .env.example .env && echo "Created .env from .env.example — review it before use")
	pip install -e ".[hospital]"
	cd frontend && npm install

# ── Development (both processes, CTRL-C stops both) ───────────────────────────
dev:
	@[ -f .env ] || (echo "Run 'make install' first to create .env"; exit 1)
	@echo ""
	@echo "  Backend  →  http://localhost:8000"
	@echo "  Frontend →  http://localhost:5173   (open this in your browser)"
	@echo ""
	@echo "  Press CTRL-C to stop both."
	@echo ""
	@trap 'kill 0' INT; \
	  uvicorn hospital.main:app --reload --port 8000 & \
	  cd frontend && npm run dev; \
	  wait

# ── Individual services ───────────────────────────────────────────────────────
backend:
	uvicorn hospital.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	python -m pytest tests/hospital/ -q
	cd frontend && npm run test -- --run

# ── Production build ──────────────────────────────────────────────────────────
build:
	cd frontend && npm run build
