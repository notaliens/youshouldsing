import audioread
import distutils
import optparse
import os
import shutil
import sys
import subprocess
import time
import transaction
import logging

from ZODB.blob import Blob

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )
from pyramid.traversal import find_resource
from yss.utils import get_redis

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
        logger.info('Waiting for another recording')
        pathandtime = redis.blpop('yss.new-recordings', 0)[1] # blocking pop
        path = pathandtime.decode('utf-8')
        try:
            path, enqueued = path.rsplit('|', 1)
        except ValueError:
            enqueued = time.time()
        else:
            enqueued = float(enqueued)
        logger.info(f'Received request for {path}')
        time.sleep(0.25)
        transaction.abort()
        try:
            recording = find_resource(root, path)
        except KeyError:
            logger.warning(f'Could not find {path}')
        else:
            try:
                if not bool(recording.dry_blob):
                    logger.warning(f'not committed yet: {path}')
                    redis.rpush('yss.new-recordings', path)
                else:
                    logger.info(f'Processing {path} enqueued at {enqueued}')
                    postprocess(recording, redis)
                    end = time.time()
                    logger.info(
                        f'Time from enqeue-to-done for {path}: {end-enqueued}')
            except:
                logger.warning(
                    f'Unexpected error when processing {path}',
                    exc_info=True
                )
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
    roid = recording.__oid__
    mixstart = time.time()
    try:
        progress_key = f'mixprogress-{roid}'
        logger.info(f'Progress key is {progress_key}')
        redis.hmset(
            progress_key, {'pct':1, 'status':'Preparing'}
        )
        redis.expire(progress_key, 1200) # expire in 20 minutes
        logger.info(f'Changing dir to {tmpdir}')
        try:
            os.chdir(tmpdir)
        except FileNotFoundError:
            os.makedirs(tmpdir)
            os.chdir(tmpdir)
        dry_webm = recording.dry_blob.committed()
        open('dry_blob_filename', 'w').write(dry_webm)
        redis.hmset(
            progress_key, {'pct':10, 'status':'Extracting dry mic audio'}
        )
        soxexe = distutils.spawn.find_executable('sox')
        ffmpegexe = distutils.spawn.find_executable('ffmpeg')

        ffextract = [
            ffmpegexe,
            "-threads", "4",
            '-thread_queue_size', '512',
            "-y", # clobber
            "-i", dry_webm,
            "-vn", # no video
            "-ar", "48000", # it will always be 48K from chrome
            "-acodec", "copy",
            "-f", "opus",
            "micdry.opus"
            ]

        logger.info(f'Extracting dry mic into {tmpdir}/micdry.opus using')
        logger.info(' '.join(ffextract))

        pffextract = subprocess.Popen(
            ffextract,
            shell=False
        )
        pffextract.communicate()
        duration = audioread.audio_open('micdry.opus').duration

        sox2wet = [
            soxexe,
            '--buffer', '20000',
            '-t', 'opus',
            '-v', '0.1', # pertains to micdry.opus to prevent clipping
            'micdry.opus',
            '-r', '48000',
            '-t', 'flac',
            '-',
        ]
        # compressor always enabled
        sox2wet.extend(
            "compand 0.3,1 -90,-90,-70,-70,-60,-20,0,0 -5 0 0.2".split(' ')
            )
        if 'effect-reverb' in recording.effects:
            sox2wet.extend(["reverb", "40"])
        if 'effect-chorus' in recording.effects:
            s = "chorus 0.6 0.9 50.0 0.4 0.25 2.0 -t 60.0 0.32 0.4 1.3 -s"
            sox2wet.extend(s.split(' '))
        song_audio_filename = recording.song.blob.committed()
        open('song_audio_filename', 'w').write(song_audio_filename)
        musicvolume = recording.musicvolume
        latency = recording.latency
        sox2mixed = [
            soxexe,
            '--buffer', '20000',
            '-t', 'flac',
            '-',
            "-M",
            "-t", "opus",
            # applies to song_audio_filename (0.5 is default on slider)
            "-v", f"{float(musicvolume)}", # x5 is a guess
            song_audio_filename,
            '-t', 'flac',
            "-r", "48000",
            '-',
        ]
        sox2mixed.extend(["trim", "0", str(duration)])
        if latency:
            # apply latency adj, must come before other options or voice is
            # doubled
            sox2mixed.extend(['delay', "0", str(latency)])
        # center vocals (see https://stackoverflow.com/questions/14950823/sox-exe-mixing-mono-vocals-with-stereo-music)
        sox2mixed.extend(["remix", "-m", "1,2", "2,1"])

        ffm2webm = [
            ffmpegexe,
            "-threads", "4",
            '-thread_queue_size', '512',
            "-y", # clobber
            "-i", dry_webm,
            "-i", "pipe:",
            # vp8/opus combination supported by both FF and chrome
            "-c:a", "libopus",
            "-map", "1:a:0",
            "-b:a", "128000",
            "-vbr", "on",
            "-compression_level", "10",
            "-shortest",
            ]
        if recording.show_camera:
            ffm2webm.extend([
                "-c:v", "vp8",
                "-map", "0:v:0?", # ? at end makes it opt (recs with no cam)
                ])
        else:
            ffm2webm.append('-vn') # no video
        ffm2webm.extend([
            # https://stackoverflow.com/questions/20665982/convert-videos-to-webm-via-ffmpeg-faster
            '-cpu-used', '8', # gofast (default is 1, quality suffers)
            '-deadline', 'realtime', # gofast
            'mixed.webm'
        ])

        redis.hmset(
            progress_key, {'pct':60, 'status':'Creating mix'}
        )

        logger.info(f'Creating mix in {tmpdir}/mixed.webm')
        logger.info('pipeline:')
        logger.info(
            ' '.join(sox2wet) + ' | ' +
            ' '.join(sox2mixed) + ' | ' +
            ' '.join(ffm2webm)
        )

        # look at it go
        psox2wet = subprocess.Popen(
            sox2wet,
            stdout=subprocess.PIPE,
            shell=False
        )

        psox2mixed = subprocess.Popen(
            sox2mixed,
            stdin=psox2wet.stdout,
            stdout=subprocess.PIPE,
            shell=False
        )

        pff2webm = subprocess.Popen(
            ffm2webm,
            stdin=psox2mixed.stdout,
            shell=False,
            )

        psox2wet.stdout.close()
        psox2mixed.stdout.close()
        pff2webm.communicate()
        logger.info(f'finished mixing {tmpdir}')

        recording.mixed_blob = Blob()
        redis.hmset(
            progress_key, {'pct':90, 'status':'Saving final mix'}
        )
        logger.info(f'Copying final mix to mixed blob')
        with recording.mixed_blob.open("w") as saveto:
            with open("mixed.webm", "rb") as savefrom:
                shutil.copyfileobj(savefrom, saveto)
        logger.info("%s/%s" % (tmpdir, "mixed.webm"))
        recording.remixing = False
        transaction.commit()
        open('mixed_blob_filename', 'w').write(recording.mixed_blob.committed())
        redis.hmset(
            progress_key, {'pct':100, 'status':'Finished'}
        )
        # don't remove tempdir until commit succeeds
        #shutil.rmtree(tmpdir, ignore_errors=True)
    except FileNotFoundError:
        logger.warning('no such file or dir when chdir')
        redis.hmset(
            progress_key,
            {'pct':-1, 'status':'Mix failed; temporary files missing'}
        )
        redis.persist(progress_key)
        recording.postproc_failure = True # currently not exposed
    finally:
        mixend = time.time()
        logger.info(f'total mix time: {mixend-mixstart}')
        os.chdir(curdir)
