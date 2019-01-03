import json
import pprint
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

def format_timings(timings):
    timings = json.loads(timings)
    formatted = []
    twodecs = '%.3f'
    for start, end, words in timings:
        formatted_start = twodecs % (start or 0)
        formatted_end = twodecs % (end or 0)
        formatted_words = []
        for wordstart, word in words:
            formatted_words.append(
                [twodecs % wordstart,
                 word]
                )
        formatted.append([formatted_start, formatted_end, formatted_words])
    return pprint.pformat(formatted, width=50)

def authentication_type(request):
    if request.user is not None:
        if request.user.__name__.startswith('twitter.com_'):
            return 'twitter'
        if request.user.__name__.startswith('accounts.google.com_'):
            return 'google'
