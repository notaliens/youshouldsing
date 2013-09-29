import redis

def get_redis(request):
    settings = request.registry.settings
    host = settings.get('redis.host', 'localhost')
    port = int(settings.get('redis.port', 6379))
    db = int(settings.get('redis.db', 0))
    db = redis.StrictRedis(host=host, port=port, db=db)
    return db
