import optparse
import os
import sys
import time
import transaction
import logging

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )

from substanced.event import ObjectModified
from substanced.objectmap import find_objectmap

from yss.interfaces import UnrecoverableError
from yss.utils import get_redis
from yss.recordings.mixer import FFMpegMixer

logger = logging.getLogger('postproc')

def main(argv=sys.argv):
    def usage(msg):
        print (msg)
        sys.exit(2)
    description = "Mix new recordings as they are made."
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
    objectmap = find_objectmap(root)
    while True:
        logger.info('Waiting for another recording')
        oidandtime = redis.blpop('yss.new-recordings', 0)[1] # blocking pop
        oidandtime = oidandtime.decode('utf-8')
        try:
            oid, enqueued = oidandtime.rsplit('|', 1)
        except ValueError:
            oid = int(oidandtime)
            enqueued = time.time()
        else:
            oid = int(oid)
            enqueued = float(enqueued)
        logger.info(f'Received request for {oid}')
        time.sleep(0.25)
        transaction.abort()
        recording = objectmap.object_for(oid)
        if recording is None:
            logger.warning(f'Could not find {oid}')
        else:
            try:
                if not bool(recording.dry_blob):
                    logger.warning(f'not committed yet: {recording.__name__}')
                    redis.rpush('yss.new-recordings', oidandtime)
                else:
                    logger.info(f'Processing {oid} enqueued at {enqueued}')
                    postprocess(recording, redis, env)
                    end = time.time()
                    logger.info(
                        f'Time from enqeue-to-done for {oid}: {end-enqueued}')
            except UnrecoverableError:
                logger.warning(
                    f'Unrecoverable error when processing {oid}',
                    exc_info=True
                )
                redis.hmset(
                    recording.mixprogress_key,
                    {'pct':-1, 'status':'Unrecoverable error'}
                )
            except:
                logger.warning(
                    f'Unexpected error when processing {oid}',
                    exc_info=True
                )
                redis.hmset(
                    recording.mixprogress_key,
                    {'pct':-1, 'status':'Mix failed; unexpected error'}
                )
                redis.persist(recording.mixprogress_key) # clear only on good
                redis.rpush('yss.new-recordings', oidandtime)
                raise

def postprocess(recording, redis, env):
    tmpdir = recording.tmpfolder
    curdir = os.getcwd()
    mixstart = time.time()
    registry = env['registry']
    try:
        progress_key = recording.mixprogress_key
        logger.info(f'Progress key is {progress_key}')
        redis.expire(progress_key, 1200) # expire in 20 minutes
        logger.info(f'Changing dir to {tmpdir}')
        try:
            os.chdir(tmpdir)
        except FileNotFoundError:
            os.makedirs(tmpdir)
            os.chdir(tmpdir)
        dry_webm = recording.dry_blob.committed()
        song_audio_filename = recording.song.blob.committed()
        open('dry_blob_filename', 'w').write(dry_webm)
        open('song_audio_filename', 'w').write(song_audio_filename)
        mixer = FFMpegMixer(recording)
        outfile = 'remixed.webm'
        try:
            for i, prog in enumerate(mixer.progress(outfile)):
                percent = prog['pct']
                fps = prog['fps']
                logger.debug(f'Mixing percent {percent} after {i+1} progress calls')
                if fps:
                    status = f'Mixing ({fps} fps)'
                else:
                    status = 'Mixing'
                redis.hmset(
                    progress_key, {'pct':percent, 'status':status}
                )
        except UnrecoverableError:
            recording.enqueued = False
            transaction.commit()
            raise
        else:
            with open(outfile, 'rb') as savefrom:
                logger.info(f'Remixed {recording.__name__}')
                recording.set_remixing(savefrom)
                recording.enqueued = False
                event = ObjectModified(recording)
                registry.subscribers((event, recording), None)

            transaction.commit()
            open('remixing_blob_filename', 'w').write(
                recording.remixing_blob.committed()
            )
            redis.hmset(
                progress_key, {'pct':100, 'status':'Finished'}
            )

    finally:
        mixend = time.time()
        logger.info(f'total mix time: {mixend-mixstart}')
        os.chdir(curdir)
