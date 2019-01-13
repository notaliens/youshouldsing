import distutils
import optparse
import os
import shutil
import shlex
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

from substanced.objectmap import find_objectmap

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
                    postprocess(recording, redis)
                    end = time.time()
                    logger.info(
                        f'Time from enqeue-to-done for {oid}: {end-enqueued}')
            except:
                logger.warning(
                    f'Unexpected error when processing {oid}',
                    exc_info=True
                )
                progress_key = f'mixprogress-{recording.__oid__}'
                redis.hmset(
                    progress_key,
                    {'pct':-1, 'status':'Mix failed; unexpected error'}
                )
                redis.persist(progress_key) # clear only on good
                redis.rpush('yss.new-recordings', oidandtime)
                raise

def postprocess(recording, redis):
    tmpdir = recording.tmpfolder
    curdir = os.getcwd()
    mixstart = time.time()
    try:
        progress_key = f'mixprogress-{recording.__oid__}'
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
            progress_key, {'pct':50, 'status':'Mixing'}
        )
        ffmpegexe = distutils.spawn.find_executable('ffmpeg')
        song_audio_filename = recording.song.blob.committed()
        open('song_audio_filename', 'w').write(song_audio_filename)
        ffmix = [
            ffmpegexe,
            "-threads", "4",
            '-thread_queue_size', '512',
            "-y", # clobber
            "-i", dry_webm,
            "-i", song_audio_filename,
            "-shortest",
            "-b:a", "128000",
            "-vbr", "on",
            "-compression_level", "10",
            ]
        webmfilter = []
        songfilter = []
        if recording.latency:
            latency = recording.latency # float
            abslatency = abs(recording.latency)
            #latency_ms = int(abslatency*1000)
            #adelay = f'adelay={latency_ms}|{latency_ms}' #ms
            atrim =f'atrim={abslatency}' #seconds
            if abslatency == latency: # fix mic audio ahead of backing track
                songfilter.append(atrim) # mono
            else: # fix backing track ahead of mic audio
                webmfilter.append(atrim) # stereo
        songfilter.append(f'volume={recording.musicvolume}')

        webmfilter.extend([
            'acompressor', # compress
            'dynaudnorm' # windowed-normalize (not peak)
            # alternative to dynaudnorm (sounds better but introduces vid lat)
            # 'ladspa=vlevel-ladspa:vlevel_mono'
        ])
        if 'effect-reverb' in recording.effects:
            # probably too hall-y but #7 is verb type and #27 is "large room"
            webmfilter.append('ladspa=file=tap_reverb:tap_reverb:c=c7=27') 
        if 'effect-chorus' in recording.effects:
            webmfilter.append(
                'chorus=0.5:0.9:50|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3')

        # NB: duration=shortest required in aout when no video, because ffmpeg
        # cant tell audio duration from webm container even with -shortest,
        # and mixes that include -vn become as long as the backing track
        allfilter = (f"[0:a]{','.join(webmfilter)}[a0]; "
                     f"[1:a]{','.join(songfilter)}[a1]; "
                     f"[a0][a1]amix=inputs=2:duration=shortest[aout]")

        ffmix.extend([
            '-filter_complex',
            allfilter,
            '-map', '[aout]',
            '-ac', '2',
            "-ar", "48000", # it will always be 48K from chrome
            ])
        if recording.show_camera:
            ffmix.extend([
                "-c:v", "vp8",
                "-map", "0:v:0?", # ? at end makes it opt (recs with no cam)
                ])
        else:
            ffmix.extend([
                '-vn',
            ]) # no video

        ffmix.extend([
            # https://stackoverflow.com/questions/20665982/convert-videos-to-webm-via-ffmpeg-faster
            '-cpu-used', '8', # gofast (default is 1, quality suffers)
            '-deadline', 'realtime', # gofast
            'mixed.webm'
        ])

        logger.info(f'Mixing using')
        logger.info(' '.join([shlex.quote(s) for s in ffmix]))

        pffextract = subprocess.Popen(
            ffmix,
            shell=False
        )
        pffextract.communicate()

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
        raise
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

"""
Show available plugins in tap_reverb
ffmpeg -i dry.opus -filter ladspa=file=tap_reverb -f null /dev/null

Show options for tap_reverb:tap_reverb
ffmpeg -i dry.opus -filter ladspa=f=tap_reverb:p=tap_reverb:c=help -f null /dev/null

[Parsed_ladspa_0 @ 0x558c85e9c940] The 'tap_reverb' plugin has the following input controls:
[Parsed_ladspa_0 @ 0x558c85e9c940] c0: Decay [ms] [<float>, min: 0.000000, max: 10000.000000 (default 2500.000000)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c1: Dry Level [dB] [<float>, min: -70.000000, max: 10.000000 (default 0.000000)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c2: Wet Level [dB] [<float>, min: -70.000000, max: 10.000000 (default 0.000000)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c3: Comb Filters [toggled (1 or 0) (default 1)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c4: Allpass Filters [toggled (1 or 0) (default 1)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c5: Bandpass Filter [toggled (1 or 0) (default 1)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c6: Enhanced Stereo [toggled (1 or 0) (default 1)]
[Parsed_ladspa_0 @ 0x558c85e9c940] c7: Reverb Type [<int>, min: 0, max: 42 (default 0)]

"""
