import optparse
import os
import shutil
import sys
import time
import transaction
import logging

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
        path = redis.blpop('yss.new-recordings', 0)[1] # blocking pop
        path = path.decode('utf-8')
        time.sleep(1)
        transaction.abort()
        try:
            recording = find_resource(root, path)
        except KeyError:
            logger.warning('Cold not find %s' % path)
            
        else:
            try:
                if not bool(recording.dry_blob):
                    # not committed yet
                    redis.rpush('yss.new_recordings', path)
                else:
                    postprocess(recording, redis)
            except:
                progress_key = f'mixprogress-{recording.__name__}'
                redis.hmset(
                    progress_key,
                    {'pct':-1, 'status':'Mix failed; unexpected error'}
                )
                redis.persist(progress_key) # clear only on good
                redis.rpush('yss.new-recordings', path)
                raise

def postprocess(recording, redis):
    tmpdir = recording.tmpfolder
    curdir = os.getcwd()
    try:
        progress_key = f'mixprogress-{recording.__name__}'
        redis.hmset(
            progress_key, {'pct':1, 'status':'Preparing'}
        )
        redis.expire(progress_key, 120) # expire in 2 minutes
        print ('Changing dir to %s' % tmpdir)
        try:
            os.chdir(tmpdir)
        except FileNotFoundError:
            os.makedirs(tmpdir)
            os.chdir(tmpdir)
        dry_webm = recording.dry_blob.committed()
        # sox can't deal with opus audio, so temp transcode to mp3
        redis.hmset(
            progress_key, {'pct':10, 'status':'Extracting dry mic audio'}
        )
        ffmpeg(
            "-y",
            "-i", dry_webm,
            "-vn", # no video
            "-ar", "44100",
            "-y", # clobber
            "micdry.mp3"
            )
        err = StringIO()
        samples = None
        soxargs = [
            "-V",
            "--clobber",
            "micdry.mp3",
            "-r", "44100",
            "micwet.mp3",
        ]
        # compressor always enabled
        soxargs.extend(
            "compand 0.3,1 -90,-90,-70,-70,-60,-20,0,0 -5 0 0.2".split(' ')
            )
        if 'effect-reverb' in recording.effects:
            soxargs.extend(["reverb", "45"])
        if 'effect-chorus' in recording.effects:
            s = "chorus 0.6 0.9 50.0 0.4 0.25 2.0 -t 60.0 0.32 0.4 1.3 -s"
            soxargs.extend(s.split(' '))
        redis.hmset(
            progress_key, {'pct':30, 'status':'Applying effects'}
        )
        sox(
            soxargs,
            _err=err,
        )
        # stderr will contain the duration that we can use to trim the file
        # to its proper length in the next sox command, which does the
        # mixing
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
        musicvolume = recording.musicvolume
        soxargs = [
            "-V",
            "--clobber",
            "-m", "micwet.mp3",
            "-t", "mp3",
            "-v", f"{float(musicvolume)}", # applies to song_audio_filename (0.5 is default on slider)
            song_audio_filename,
            "mixed.mp3",
            "remix", "-m", "1,2", "2,1", # center vocals (see https://stackoverflow.com/questions/14950823/sox-exe-mixing-mono-vocals-with-stereo-music)
        ]
        if samples:
            soxargs.extend(['trim', '0s', f'{samples}s'])
        redis.hmset(
            progress_key, {'pct':50, 'status':'Rebalancing audio'}
        )
        sox(soxargs)
        redis.hmset(
            progress_key, {'pct':60, 'status':'Creating final mix'}
        )
        ffmpeg(
            "-y", # clobber
            "-i", dry_webm,
            "-i", "mixed.mp3",
            # vp8/opus combination supported by both FF and chrome
            "-c:v", "vp8",
            "-c:a", "libopus",
            "-map", "0:v:0?", # ? at end makes it optional (recs with no video)
            "-map", "1:a:0",
            "-shortest",
            "mixed.webm"
        )
        recording.mixed_blob = Blob()
        redis.hmset(
            progress_key, {'pct':90, 'status':'Saving final mix'}
        )
        with recording.mixed_blob.open("w") as saveto:
            with open("mixed.webm", "rb") as savefrom:
                shutil.copyfileobj(savefrom, saveto)
        print ("%s/%s" % (tmpdir, "mixed.webm"))
        transaction.commit()
        redis.hmset(
            progress_key, {'pct':100, 'status':'Finished'}
        )
        # don't remove tempdir until commit succeeds
        #shutil.rmtree(tmpdir)
    except FileNotFoundError:
        # no such file or dir when chdir
        redis.hmset(
            progress_key,
            {'pct':-1, 'status':'Mix failed; temporary files missing'}
        )
        redis.persist(progress_key)
        recording.postproc_failure = True # currently not exposed
    finally:
        os.chdir(curdir)


