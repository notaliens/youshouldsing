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

from io import StringIO

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
        # in javascript somehow, but this is probably where we
        # will apply reverb anyway, so the cost is already kinda sunk
        err = StringIO()
        sox(
            "-V",
            "--clobber",
            "audio.wav",
            "-r", "44100",
            "rerated.wav",
            _err=err,
        )
        # stderr will contain the duration that we can use to trim the file
        # to its proper length in the next sox command, which does the
        # mixing
        samples = None
        errlines = err.getvalue().split('\n')
        for line in errlines:
            if line.startswith('Duration'):
                duration = line.split(':', 1)[1]
                duration.strip()
                duration, samples = duration.split('=', 1)
                duration = duration.strip()
                samples = samples.strip()
                samples = samples.split(' ', 1)[0].strip()
                samples = int(samples)
                break
        sox(
            "-V",
            "--clobber",
            "-m", "rerated.wav",
            "-t", "mp3",
            "-v", "0.15",
            committed,
            "mixed.wav",
            "trim" if samples is not None else "",
            "0s" if samples is not None else "",
            f"{samples}s" if samples is not None else "",
        )
        ffmpeg(
            "-y",
            "-i", "mixed.wav",
            "-f", "image2",
            "-r", f"{framerate}",
            "-i", "frame%d.png",
            "-acodec", "mp3",
            "-shortest",
            "video.mp4"
        )
        recording.blob = Blob()
        with recording.blob.open("w") as saveto:
            with open("video.mp4", "rb") as savefrom:
                shutil.copyfileobj(savefrom, saveto)
        print ("%s/%s" % (tmpdir, "video.mp4"))
        transaction.commit()
        # don't remove tempdir until commit succeeds
        #shutil.rmtree(tmpdir)
    except FileNotFoundError:
        # no such file or dir when chdir
        recording.postproc_failure = True # currently not exposed
    finally:
        os.chdir(curdir)


