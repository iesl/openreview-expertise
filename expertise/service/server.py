from expertise.service import (
    create_app, create_celery, create_redis
)

app = create_app()
redis_conn_pool = create_redis(app)
celery_app = create_celery(app)
