import optparse
import os
import shutil
import sys
import time
import transaction
import logging
import json

from sh import ffmpeg

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )
from pyramid.traversal import find_resource
from yss.utils import get_redis, format_timings

from google.cloud import storage
from google.cloud import speech
from google.cloud.speech import enums as speech_enums
from google.cloud.speech import types as speech_types

logger = logging.getLogger('retime')

def main(argv=sys.argv):
    def usage(msg):
        print (msg)
        sys.exit(2)
    description = "Handle new lyric retimings as they are made."
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
        logger.info('Waiting for another retiming')
        path = redis.blpop('yss.new-retimings', 0)[1] # blocking pop
        path = path.decode('utf-8')
        time.sleep(1)
        transaction.abort()
        try:
            song = find_resource(root, path)
        except KeyError:
            logger.warning('Could not find %s' % path)
            
        else:
            progress_key = f'retimeprogress-{song.__name__}'
            try:
                if not bool(song.retiming_blob):
                    # not committed yet
                    redis.rpush('yss.new-retimings', path)
                else:
                    retime(song, redis, env)
            except SystemExit:
                redis.persist(progress_key) # clear only on good
                redis.rpush('yss.new-retimings', path)
                raise
            except:
                redis.hmset(
                    progress_key,
                    {'pct':-1, 'status':'Retiming failed; unexpected error'}
                )
                redis.persist(progress_key) # clear only on good
                redis.rpush('yss.new-retimings', path)
                raise

def get_retime_tempdir(registry, song_id):
    retime_dir = registry.settings['yss.retime_dir']
    return os.path.abspath(os.path.join(retime_dir, song_id))
            
def retime(song, redis, env):
    tmpdir = get_retime_tempdir(
        env['registry'],
        song.__name__.strip('/').strip('\\\\').strip('..')
    )
    curdir = os.getcwd()
    try:
        progress_key = f'retimeprogress-{song.__name__}'
        redis.hmset(
            progress_key, {'pct':1, 'status':'Preparing'}
        )
        redis.expire(progress_key, 1200) # expire in 20 minutes
        print ('Changing dir to %s' % tmpdir)
        try:
            os.chdir(tmpdir)
        except FileNotFoundError:
            os.makedirs(tmpdir)
            os.chdir(tmpdir)
        webm_filename = song.retiming_blob.committed()

        gproject = os.environ['YSS_GOOGLE_STORAGE_PROJECT']
        gbucket = os.environ['YSS_GOOGLE_STORAGE_BUCKET']
        blobname = f'{song.__name__}.retime'
        gsuri = f'gs://{gbucket}/{blobname}'

        opus_filename = os.path.join(tmpdir, 'retime.opus')

        logger.info('Converting webm to opus') # XX should just copy audio

        ffmpeg(
            "-y",
            "-i", webm_filename,
            "-vn", # no video
            "-ar", "48000",
            "-y", # clobber
            opus_filename,
            )

        logger.info('Finished converting webm to opus')

        client = storage.Client(gproject)
        bucket = client.bucket(gbucket)
        blob = bucket.blob(blobname)
        logger.info('Uploading timing track to gcloud...')
        blob.upload_from_file(
            open(opus_filename, 'rb'),
            content_type='audio/opus',
        )
        logger.info('Finished uploading timing track...')

        client = speech.SpeechClient()

        audio = speech_types.RecognitionAudio(uri=gsuri)
        config = speech_types.RecognitionConfig(
            encoding=speech_enums.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=48000,
            language_code=song.language,
            enable_word_time_offsets=True,
        )

        logger.info('Waiting for speech recognition to complete')
        operation = client.long_running_recognize(config, audio)
        # google.api_core.exceptions.GoogleAPICallError: None
        # Unexpected state: Long-running operation had neither response
        # nor error set.
        # doing add_done_callback and checking for status is pointless,
        # it returns 0 then 100 for percent complete
        redis.hmset(
            progress_key,
            {'pct':50,
             'status':'Recognizing speech',
             'done':1,
            }
        )
        response = operation.result(timeout=7200)
        logger.info('Speech recognition operation completed')
        timings = speech_results_to_timings(response.results, 7)
        alt_timings = json.dumps(timings, indent=2)
        song.alt_timings = alt_timings
        formatted_timings = format_timings(alt_timings)
        redis.hmset(
            progress_key,
            {'pct':100,
             'status':'Finished',
             'timings':alt_timings,
             'formatted_timings':formatted_timings,
             'done':1,
            }
        )
        song.retiming = False
        song.retiming_blob = None
        transaction.commit()
        shutil.rmtree(tmpdir, ignore_errors=True)
    except FileNotFoundError:
        # no such file or dir when chdir
        redis.hmset(
            progress_key,
            {'pct':-1, 'status':'Retime failed; temporary files missing'}
        )
        redis.persist(progress_key)
        song.retime_failure = True # currently not exposed
    finally:
        os.chdir(curdir)

def speech_results_to_timings(speech_results, max_words_per_line):
    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.
    timings = []
    words = []
    for result in speech_results:
        # we'd like to be able to get hints about where lines end
        # naturally by relying on this result batching, but let's get it
        # working first
        words.extend(result.alternatives[0].words)

    line_start = 0
    word_end = 0
    word_timings = []

    for i, word in enumerate(words):
        start_secs = word.start_time.seconds
        start_ns = word.start_time.nanos
        start_ms = round(start_ns/1e+9, 3)
        word_start = start_secs + start_ms
        padding = ' '
        if line_start is None:
            line_start = word_start
            padding = ''
        end_secs = word.end_time.seconds
        end_ns = word.end_time.nanos
        end_ms = round(end_ns/1e+9, 3)
        word_end = end_secs + end_ms

        word_timings.append([word_start - line_start, padding + word.word])

        needs_line_break = i and (i % max_words_per_line == 0)

        if needs_line_break:
            timing = [line_start, word_end, word_timings]
            timings.append(timing)
            line_start = None
            word_timings = []

    if line_start is not None: # if we didn't catch it at a modulo
        timings.append([line_start, word_end, word_timings]) # stragglers

    return timings
