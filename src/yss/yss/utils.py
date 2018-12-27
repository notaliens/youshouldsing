import redis

def get_redis(request):
    settings = request.registry.settings
    host = settings.get('redis.host', 'localhost')
    port = int(settings.get('redis.port', 6379))
    db = int(settings.get('redis.db', 0))
    db = redis.StrictRedis(host=host, port=port, db=db)
    return db

def decode_redis_hash(d):
    decoded = {}
    for k, v in d.items():
        # eyeroll
        newkey = k.decode('utf-8')
        if isinstance(v, bytes):
            v = v.decode('utf-8')
        decoded[newkey] = v
    return decoded
