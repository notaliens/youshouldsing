import hashlib
import os
import tempfile
import shlex
import shutil
import subprocess
import sys

def cdgmp3_to_webm(cdg, mp3):
    tmpdir = tempfile.mkdtemp()
    cwd = os.path.abspath(os.path.normpath(os.getcwd()))
    try:
        md5 = hashlib.md5()
        f = open(mp3, 'rb')
        while True:
            data = f.read(1<<19)
            if not data:
                break
            md5.update(data)
        hexdigest = md5.hexdigest()
        os.chdir(tmpdir)
        songname, _ = os.path.splitext(os.path.basename(cdg))
        command = [
            'mp3info',
            '-p',
            r'%t\t%a\t%g\t%y\n',
            mp3,
            ]
        print (' '.join([ shlex.quote(s) for s in command ]))
        proc = subprocess.Popen(command, universal_newlines=True, stdout=subprocess.PIPE)
        stdout, _ = proc.communicate()
        title, artist, genre, year = stdout.rstrip('\n').split('\t', 3)
        filetitle = title.replace(' ', '-').lower()
        songfn = os.path.join(cwd, 'sf-'+filetitle+'-'+hexdigest+'.webm')
        if os.path.exists(songfn):
            return
        command = [
            '/usr/bin/python',
            '/usr/lib/python2.7/dist-packages/pycdg.py',
            '--dump=tmp#####.jpeg',
            '--dump-fps=10',
            cdg,
            ]
        print (' '.join([ shlex.quote(s) for s in command ]))
        proc = subprocess.Popen(command)
        proc.communicate()
        command = [
            'ffmpeg',
            '-y',
            '-threads', '4',
            '-thread_queue_size', '4096',
            '-r', '10',
            '-f', 'image2',
            '-s', '640x480',
            '-i', r'tmp%05d.jpeg',
            '-i', mp3,
            '-vcodec', 'vp8',
            '-acodec', 'libopus',
            '-metadata', f'title="{title}"',
            '-metadata', f'artist="{artist}"',
            '-metadata', f'year="{year}"',
            '-metadata', f'genre="{genre}"',
            '-ar', '48000',
            "-b:a", "128000",
            "-vbr", "on",
            "-compression_level", "10",
            '-cpu-used', '8', # gofast (default 1, qual suffers)
            '-deadline', 'realtime', # gofast
            '-f', 'webm',
            songfn,
            ]
        print (' '.join([ shlex.quote(s) for s in command ]))
        proc = subprocess.Popen(command)
        stdout = proc.communicate()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.chdir(cwd)

if __name__ == '__main__':
    cdgs = sys.argv[1:]
    for cdg in cdgs:
        fn = os.path.abspath(os.path.normpath(cdg))
        basename, _ = os.path.splitext(fn)
        cdgmp3_to_webm(basename+'.cdg', basename+'.mp3')
