from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "moskit_import",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.import_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # confirma ack só após conclusão — evita perda em crash
    worker_prefetch_multiplier=1,  # um task por worker por vez — jobs pesados
)
