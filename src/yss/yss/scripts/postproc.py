import optparse
import sys
import time
import transaction

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )
from pyramid.traversal import find_resource
from ..utils import get_redis


def main(argv=sys.argv):
    def usage(msg):
        print msg
        sys.exit(2)
    description = "Postprocess new recordings as they are made."
    usage = "usage: %prog config_uri"
    parser = optparse.OptionParser(usage, description=description)
    opts, args = parser.parse_args(argv[1:])
    try:
        config_uri = args[0]
    except KeyError:
        usage('Requires a config_uri as an argument')

    setup_logging(config_uri)
    env = bootstrap(config_uri)
    root = env['root']
    redis = get_redis(env['request'])
    while True:
        path = redis.blpop('yss.new-recordings', 0)[1]
        time.sleep(1)
        transaction.abort()
        recording = find_resource(root, path)
        print "Got it!", path, recording
