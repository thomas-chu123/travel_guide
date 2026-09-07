.PHONY: api web worker check

api:
	cd backend && uvicorn app.main:app --reload

web:
	cd frontend && npm run dev

worker:
	cd backend && python -m worker.main

check:
	python3 -m compileall -q backend
	cd frontend && npm run typecheck
