web: alembic upgrade head && gunicorn -k uvicorn.workers.UvicornWorker app.main:app --workers 4 --bind 0.0.0.0:$PORT --timeout 120
worker: celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
beat: celery -A app.workers.celery_app beat --loglevel=info
