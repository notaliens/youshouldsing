import optparse
import os
import subprocess
import sys

def main(argv=sys.argv):
    description = "Convert a midi file to mp3"
    usage = "usage: %prog [options] input_filenames"
    parser = optparse.OptionParser(usage, description=description)
    parser.add_option(
        '-e',
        '--extension',
        dest='extension',
        help='Use this extension instead of .mp3 when generating mp3 files'
        )
    parser.add_option(
        '-o',
        '--outdir',
        dest='outdir',
        help='Use this directory to output .mp3 files to'
        )
    opts, args = parser.parse_args(argv[1:])
    ext = opts.extension or '.mp3'
    outdir = opts.outdir or os.getcwd()
    for input_filename in args:
        basename, ext = os.path.splitext(os.path.basename(input_filename))
        wav_filename = basename + '.wav'
        output_filename = os.path.join(outdir, wav_filename)
        command = ['timidity', '-Ow', '-o%s' % output_filename,
                   input_filename]
        subprocess.check_call(command)
        mp3_filename = os.path.join(outdir, basename+'.mp3')
        command2 = ['lame', output_filename, mp3_filename ]
        subprocess.check_call(command2)
        os.remove(output_filename)
