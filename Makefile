.PHONY: dev stop check test backend-test frontend-build clean

dev:
	.venv/bin/python scripts/supervisor.py

stop:
	@echo "Stopping any running Argus processes..."
	@pkill -f "RunMaster.py" || true
	@pkill -f "RunDetect.py" || true
	@pkill -f "RunTracker.py" || true
	@pkill -f "RunCrash.py" || true
	@pkill -f "camera_worker.py" || true
	@pkill -f "uvicorn app.main:app" || true
	@pkill -f "vite" || true
	@lsof -ti :10000,:10002,:10004,:10008,:10010,:8000,:5173 | xargs kill -9 2>/dev/null || true
	@echo "All Argus processes stopped."

check:
	.venv/bin/python scripts/check_env.py

test: backend-test frontend-build

backend-test:
	cd backend && PYTHONPATH=. ../.venv/bin/pytest -v

frontend-build:
	cd frontend && npm run build

clean:
	rm -rf backend/media/videos/* backend/uploads/* frontend/dist
