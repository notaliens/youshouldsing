import optparse
import os
import shutil
import subprocess
import sys
import tempfile
import transaction

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
            wav_filename = basename + '.wav'
            output_filename = os.path.join(outdir, wav_filename)
            command = ['timidity', '-Ow', '-o%s' % output_filename,
                       input_filename]
            subprocess.check_call(command)
            mp3_filename = os.path.join(outdir, basename+'.mp3')
            command2 = ['lame', output_filename, mp3_filename ]
            subprocess.check_call(command2)
            os.remove(output_filename)
            try:
                del songs[basename]
            except KeyError:
                pass
            stream = open(mp3_filename, 'rb')
            timing = ''
            title = basename
            artist = basename
            song = registry.content.create(
                'Song',
                title=title,
                artist=artist,
                timing=timing,
                stream=stream
                )
            songs[basename] = song
            transaction.commit()
    finally:
        if not opts.directory:
            shutil.rmtree(outdir, ignore_errors=True)
