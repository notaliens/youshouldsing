import hashlib
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

from yss import midi

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
    opts, args = parser.parse_args(argv[1:])
    overwrite = opts.overwrite
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
            basename, ext = os.path.splitext(os.path.basename(input_filename))
            name = basename.replace('_NifterDotCom', '')
            name = name.replace('_karaoke_songs', '')
            def errback(msg):
                print (msg)
            try:
                kardata, title, artist, lyrics, timings = get_timings(
                    input_filename
                )
            except UnicodeError:
                print ('Could not get timings for %s' % input_filename)
                continue
            if timings is None:
                print ('Could not get timings for %s' % input_filename)
                continue
            md5 = hashlib.md5()
            md5.update(kardata)
            hexdigest = md5.hexdigest()
            name = '%s-%s' % (name, hexdigest)
            if name in songs and not overwrite:
                print ('Not overwriting %s' % name)
                continue
            wav_filename = basename + '.wav'
            output_filename = os.path.join(outdir, wav_filename)
            command = [
                'timidity',
                '-tutf8',
                '-idq',
                '-Ow',
                '-o%s' % output_filename,
                input_filename,
            ]
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
            )
            #altlyrics = result.stdout.decode('utf-8', errors='replace')
            #_, lyrics = altlyrics.split('\n', 1) # drop timidity output
            mp3_filename = os.path.join(outdir, basename+'.mp3')
            command2 = ['lame', output_filename, mp3_filename ]
            subprocess.check_call(command2)
            os.remove(output_filename)
            try:
                del songs[name]
            except KeyError:
                pass
            stream = open(mp3_filename, 'rb')
            song = registry.content.create(
                'Song',
                title=title,
                artist=artist,
                lyrics=lyrics,
                timings=timings,
                audio_stream=stream,
                audio_mimetype='audio/mpeg',
                )
            songs[name] = song
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
