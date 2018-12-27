import optparse
import os
import shutil
import sys
import time
import transaction
import logging

from pyramid.traversal import find_root

from sh import ffmpeg, sox
from ZODB.blob import Blob

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )
from pyramid.traversal import find_resource
from yss.utils import get_redis

from io import StringIO

logger = logging.getLogger('postproc')

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
        except KeyError:
            logger.warning('Cold not find %s' % path)
            
        else:
            try:
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
        # sox can't deal with opus audio, so temp transcode to mp3
        ffmpeg(
            "-y",
            "-i", "recording.webm",
            "-vn", # no video
            "-ar", "44100",
            "-y", # clobber
            "micdry.mp3"
            )
        err = StringIO()
        sox(
            "-V",
            "--clobber",
            "micdry.mp3",
            "-r", "44100",
            "micverb.mp3",
            "reverb",
            "45",
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
        song_audio_filename = recording.song.blob.committed()
        sox(
            "-V",
            "--clobber",
            "-m", "micverb.mp3",
            "-t", "mp3",
            "-v", "0.15",
            song_audio_filename,
            "mixed.mp3",
            "trim" if samples is not None else "",
            "0s" if samples is not None else "",
            f"{samples}s" if samples is not None else "",
        )
        ffmpeg(
            "-y",
            "-i", "recording.webm",
            "-i", "mixed.mp3",
            # vp8/opus combination supported by both FF and chrome
            "-c:v", "vp8",
            "-c:a", "libopus",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "final.webm"
        )
        recording.blob = Blob()
        with recording.blob.open("w") as saveto:
            with open("final.webm", "rb") as savefrom:
                shutil.copyfileobj(savefrom, saveto)
        print ("%s/%s" % (tmpdir, "final.webm"))
        transaction.commit()
        # don't remove tempdir until commit succeeds
        #shutil.rmtree(tmpdir)
    except FileNotFoundError:
        # no such file or dir when chdir
        recording.postproc_failure = True # currently not exposed
    finally:
        os.chdir(curdir)


