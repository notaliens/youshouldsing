import hashlib
import logging
import optparse
import shlex
import shutil
import subprocess
import sys
import tempfile
import transaction
import slug

from pyramid.paster import (
    setup_logging,
    bootstrap,
    )
from pyramid.security import Allow, Deny

from substanced.event import ObjectModified
from substanced.util import set_acl

logger = logging.getLogger('yss')

def main(argv=sys.argv):
    def usage(msg):
        print (msg)
        sys.exit(2)
    description = "Import a set of video files into the songs folder"
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
        '--av-only',
        dest='av_only',
        help='Overwrite audio/video of songs only in songs folder (not metadata)',
        action='store_true',
        )
    opts, args = parser.parse_args(argv[1:])
    overwrite = opts.overwrite
    av_only = opts.av_only

    try:
        config_uri = args[0]
    except KeyError:
        usage('Requires a config_uri as an argument')

    outdir = opts.directory or tempfile.mkdtemp()
    setup_logging(config_uri)
    env = bootstrap(config_uri)
    root = env['root']
    registry = env['registry']
    songs = root['songs']
    restricted = songs.get('restricted')
    if restricted is None:
        restricted = registry.content.create('Folder')
        songs['restricted'] = restricted
        set_acl(
            restricted,
            [(Allow, 'system.Authenticated', ['view']),
             (Allow, 'system.Authenticated', ['yss.indexed']),
             (Deny, 'system.Everyone', ['view']),
             (Deny, 'system.Everyone', ['yss.indexed'])]
        )

    try:
        for input_filename in args[1:]:
            logging.info(input_filename)
            md5 = hashlib.md5()
            f = open(input_filename, 'rb')
            while True:
                data = f.read(1<<19)
                if not data:
                    break
                md5.update(data)
            hexdigest = md5.hexdigest()
            command = [
                'ffmpeg',
                '-i',
                input_filename,
                '-f',
                'ffmetadata',
                'pipe:1',
                ]
            print (' '.join([ shlex.quote(s) for s in command ]))
            proc = subprocess.Popen(
                command,
                universal_newlines=True,
                stdout=subprocess.PIPE,
            )
            stdout, _ = proc.communicate()
            md = {}
            for line in stdout.split('\n'):
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    md[k.lower()] = v[1:-1]
            name = slug.slug(md['title'])
            title=md['title']
            artist=md['artist']
            name = '%s-%s' % (name, hexdigest)
            if name in restricted and not (overwrite or av_only):
                logging.info('Not overwriting %s' % name)
                continue
            stream = open(input_filename, 'rb')
            if name in restricted and av_only:
                logger.info('replacing video for %s' % title)
                song = restricted[name]
                song.upload(stream)
                song.mimetype = 'video/webm'
            else:
                try:
                    del restricted[name]
                except KeyError:
                    pass
                song = registry.content.create(
                    'Song',
                    title=title,
                    artist=artist,
                    lyrics='',
                    timings='',
                    stream=stream,
                    mimetype='video/webm',
                    )
                restricted[name] = song
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
