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
from yss.utils import get_redis
from yss.interfaces import framerate


def main(argv=sys.argv):
    def usage(msg):
        print (msg)
        sys.exit(2)
    description = "Postprocess new recordings as they are made."
    parser = optparse.OptionParser(
        "usage: %prog config_uri",
        description=description
    )
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
        # blocking pop
        path = redis.blpop('yss.new-recordings', 0)[1]
        path = path.decode('utf-8')
        time.sleep(1)
        transaction.abort()
        try:
            recording = find_resource(root, path)
            postprocess(recording)
        except:
            redis.rpush('yss.new-recordings', path)
            raise


def postprocess(recording):
    tmpdir = recording.tmpfolder
    curdir = os.getcwd()
    try:
        print ('Changing dir to %s' % tmpdir)
        os.chdir(tmpdir)
        committed = recording.song.blob.committed()
        # change sample rate of mic audio to match the sample
        # rate of the source song XXX this probably should be done
        # in javascript somehow
        sox("-V", "--clobber", "audio.wav", "-r", "44100", "rerated.wav")
        sox("-V", "--clobber", "-m", "rerated.wav", "-t", "mp3", "-v", "0.15",
            committed, "mixed.wav")
        ffmpeg("-y", "-i", "mixed.wav",
               "-f", "image2", "-r", f"{framerate}", "-i", "frame%d.png",
               "-acodec", "mp3", "video.mp4")
        recording.blob = Blob()
        with recording.blob.open("w") as saveto:
            with open("video.mp4", "rb") as savefrom:
                shutil.copyfileobj(savefrom, saveto)
        print ("%s/%s" % (tmpdir, "video.mp4"))
        #shutil.rmtree(tmpdir)
        transaction.commit()
    finally:
        os.chdir(curdir)


