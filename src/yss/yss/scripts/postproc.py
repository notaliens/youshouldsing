import optparse
import os
import shutil
import sys
import time
import transaction

from sh import ffmpeg, sox
from ZODB.blob import Blob

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
        try:
            postprocess(recording)
        except:
            redis.rpush('yss.new-recorings', path)
            raise


def postprocess(recording):
    tmpdir = recording.tmpfolder
    curdir = os.getcwd()
    try:
        os.chdir(tmpdir)
        sox("-m", "audio.wav", "-t", "mp3", "-v", "0.15",
            recording.song.blob.committed(), "mixed.wav")
        ffmpeg("-i", "mixed.wav",
               "-f", "image2", "-r", "1", "-i", "frame%d.png",
               "video.ogg")
        recording.blob = Blob()
        with recording.blob.open("w") as saveto:
            with open("video.ogg") as savefrom:
                shutil.copyfileobj(savefrom, saveto)
        print "%s/%s" % (tmpdir, "video.ogg")
        #shutil.rmtree(tmpdir)
    finally:
        os.chdir(curdir)


