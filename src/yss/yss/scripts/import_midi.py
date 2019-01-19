import hashlib
import logging
import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import titlecase
import transaction
import json

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )

from substanced.event import ObjectModified

from yss.scripts import midi

logger = logging.getLogger('yss')

def main(argv=sys.argv):
    def usage(msg):
        print (msg)
        sys.exit(2)
    description = "Import a set of midi files into the songs folder"
    parser = optparse.OptionParser(
        "usage: %prog config_uri input_filenames",
        description=description
    )
    parser.add_option(
        '-d',
        '--dir',
        dest='directory',
        help='Use this directory as working directory instead of a tempdir'
        )
    parser.add_option(
        '-o',
        '--overwrite',
        dest='overwrite',
        help='Overwrite songs in the songs folder instead of skipping dupes',
        action='store_true',
        )
    parser.add_option(
        '-a',
        '--audio-only',
        dest='audio_only',
        help='Overwrite audio of songs only in songs folder (not metadata)',
        action='store_true',
        )
    opts, args = parser.parse_args(argv[1:])
    overwrite = opts.overwrite
    audio_only = opts.audio_only
    outdir = opts.directory or tempfile.mkdtemp()

    try:
        config_uri = args[0]
    except KeyError:
        usage('Requires a config_uri as an argument')

    setup_logging(config_uri)
    env = bootstrap(config_uri)
    root = env['root']
    registry = env['registry']
    songs = root['songs']

    try:
        for input_filename in args[1:]:
            logging.info(input_filename)
            basename, ext = os.path.splitext(os.path.basename(input_filename))
            name = basename.replace('_NifterDotCom', '')
            name = name.replace('_karaoke_songs', '')
            def errback(msg):
                logging.info(msg)
            try:
                kardata, title, artist, lyrics, timings = get_timings(
                    input_filename
                )
            except UnicodeError:
                logging.info('Could not get timings for %s' % input_filename)
                continue
            if timings is None:
                logging.info('Could not get timings for %s' % input_filename)
                continue
            md5 = hashlib.md5()
            md5.update(kardata)
            hexdigest = md5.hexdigest()
            name = '%s-%s' % (name, hexdigest)
            if name in songs and not (overwrite or audio_only):
                logging.info('Not overwriting %s' % name)
                continue
            wav_filename = basename + '.wav'
            output_filename = os.path.join(outdir, wav_filename)
            command = [
                'timidity',
                '--volume-compensation',
                '-tutf8',
                '-idq',
                '-Ow',
                '-s48000',
                '-o%s' % output_filename,
                input_filename,
            ]
            subprocess.run(
                command,
                check=True,
            )
            opus_filename = os.path.join(outdir, basename+'.opus')
            # NB this produces an opus file at 48Khz
            command2 = ['opusenc', output_filename, opus_filename ]
            subprocess.check_call(command2)
            os.remove(output_filename)
            stream = open(opus_filename, 'rb')
            if name in songs and audio_only:
                logger.info('replacing audio for %s' % title)
                song = songs[name]
                song.upload(stream)
                song.mimetype = 'audio/opus'
            else:
                try:
                    del songs[name]
                except KeyError:
                    pass
                song = registry.content.create(
                    'Song',
                    title=title,
                    artist=artist,
                    lyrics=lyrics,
                    timings=timings,
                    audio_stream=stream,
                    audio_mimetype='audio/opus',
                    )
                songs[name] = song
            blameme = root['performers']['blameme']
            song.uploader = blameme
            event = ObjectModified(song)
            registry.subscribers((event, song), None)
            print ('done %s, %s, %s' % (name, title, artist))
            transaction.commit()
            songs._p_jar.sync()
    finally:
        if not opts.directory:
            shutil.rmtree(outdir, ignore_errors=True)

def get_timings(input_filename):
    # Avoid needing this during venusian scan
    def errback(msg):
        print (msg)
    kardata = open(input_filename, 'rb').read()
    midifile = midi.midiParseData(
        kardata,
        errback,
        'utf-8'
        )
    if midifile is None:
        print ('Not a valid midi file %s' % input_filename)
        return
    lyrics_list = midifile.lyrics.list
    timings = []
    lyrics_text = []
    first_ms = lyrics_list[0].ms
    current_line = []
    title = ' '.join([x.capitalize() for x in input_filename.split('_')])
    artist = ''
    for i, lyric in enumerate(lyrics_list):
        if i == 0:
            title = titlecase.titlecase(lyric.text)
        if i == 1:
            artist = titlecase.titlecase(lyric.text)
        current_line.append([float(lyric.ms-first_ms)/1000, lyric.text])
        try:
            next_lyric = lyrics_list[i+1]
        except IndexError:
            next_lyric = None
        if lyric.line != getattr(next_lyric, 'line', None):
            last_ms = lyric.ms
            newline = (
                float(first_ms)/1000,
                float(last_ms)/1000,
                current_line,
                )
            timings.append(newline)
            if next_lyric:
                first_ms = next_lyric.ms
            else:
                first_ms = last_ms
            line_text = ''.join(
                [syllable[1] for syllable in current_line]
            )
            lyrics_text.append(line_text.rstrip())
            current_line = []

    timings.append(  # why do we append this
        (
            float(first_ms)/1000,
            float(lyrics_list[-1].ms)/1000,
            current_line,
            )
        )
    lyrics = '\n'.join(lyrics_text)
    return kardata, title, artist, lyrics, json.dumps(timings, indent=2)
