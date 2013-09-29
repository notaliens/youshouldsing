import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import transaction
import json

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )

def main(argv=sys.argv):
    def usage(msg):
        print msg
        sys.exit(2)
    description = "Import a set of midi files into the songs folder"
    usage = "usage: %prog config_uri input_filenames"
    parser = optparse.OptionParser(usage, description=description)
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
            if basename in songs:
                if not overwrite:
                    continue
            def errback(msg):
                print msg
            try:
                timings = get_timings(input_filename)
            except UnicodeError:
                print 'Could not get timings for %s' % input_filename
                continue
            wav_filename = basename + '.wav'
            output_filename = os.path.join(outdir, wav_filename)
            command = ['timidity', '-Ow', '-o%s' % output_filename,
                       input_filename]
            subprocess.check_call(command)
            mp3_filename = os.path.join(outdir, basename+'.mp3')
            command2 = ['lame', output_filename, mp3_filename ]
            subprocess.check_call(command2)
            os.remove(output_filename)
            name = basename.replace('_NifterDotCom', '')
            name = name.replace('_karaoke_songs', '')
            try:
                del songs[name]
            except KeyError:
                pass
            stream = open(mp3_filename, 'rb')
            artist = ''
            title = ' '.join([x.capitalize() for x in name.split('_')])
            song = registry.content.create(
                'Song',
                title=title,
                artist=artist,
                timings=timings,
                stream=stream
                )
            songs[name] = song
            transaction.commit()
            songs._p_jar.sync()
    finally:
        if not opts.directory:
            shutil.rmtree(outdir, ignore_errors=True)

def get_timings(input_filename):
    # Avoid needing this during venusian scan
    import pykar
    def errback(msg):
        print msg
    kardata = open(input_filename, 'rb').read()
    midifile = pykar.midiParseData(
        kardata,
        errback,
        ''
        )
    lyrics_list = midifile.lyrics.list
    timings = []
    last_line = lyrics_list[0].line
    first_ms = lyrics_list[0].ms
    current_line = []
    for i, lyric in enumerate(lyrics_list):
        current_line.append([float(lyric.ms-first_ms)/1000, lyric.text])
        try:
            next_lyric = lyrics_list[i+1]
        except IndexError:
            next_lyric = None
        if lyric.line != last_line:
            last_ms = lyric.ms
            timings.append(
                (
                    float(first_ms)/1000,
                    float(last_ms)/1000,
                    current_line,
                )
            )
            last_line = lyric.line
            current_line = []
            if next_lyric:
                first_ms = next_lyric.ms
            else:
                first_ms = last_ms
    timings.append(
        (
            float(first_ms)/1000,
            float(lyrics_list[-1].ms)/1000,
            current_line,
            )
        )
    return json.dumps(timings, indent=2)
