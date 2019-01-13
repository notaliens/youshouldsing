import distutils.spawn
import logging
import shlex
import re
import subprocess
import string

ffmpegexe = distutils.spawn.find_executable('ffmpeg')

logger = logging.getLogger('ffmpegmixer')

class FFMpegMixer(object):
    def __init__(self, recording):
        self.recording = recording

    def get_command(self, outfile=None):
        """ Returns a list of tokens representing a command that can be
        passed to subprocess.Popen.  If outfile is None, the stdout of
        the subprocess will be used.  Otherwise it must be a string
        representing a filename.  """
        recording = self.recording
        dry_webm_filename = recording.dry_blob.committed()
        song_audio_filename = recording.song.blob.committed()

        ffmix = [
            ffmpegexe,
            '-hide_banner',
            "-threads", "4",
            '-thread_queue_size', '512',
            "-y", # clobber
            "-i", dry_webm_filename,
            "-i", song_audio_filename,
            "-shortest",
            "-b:a", "128000",
            "-vbr", "on",
            "-compression_level", "10",
            ]
        normfilter = []
        songfilter = []
        if recording.latency:
            latency = recording.latency # float
            abslatency = abs(latency)
            #latency_ms = int(abslatency*1000)
            #adelay = f'adelay={latency_ms}|{latency_ms}' #ms
            atrim =f'atrim={abslatency}' #seconds
            if abslatency == latency:
                # fix mic audio ahead of backing track
                songfilter.append(atrim) # mono
            else:
                # fix backing track ahead of mic audio
                normfilter.append(atrim) # stereo
        if recording.voladjust:
            voladjust = recording.voladjust
            absvoladjust = abs(voladjust)
            avoladjust = f'volume={absvoladjust}'
            if absvoladjust == voladjust:
                # turn down song volume ("up for louder vocals")
                avoladjust = f'volume={1-voladjust}'
                songfilter.append(avoladjust)
                normfilter.append('volume=1.0')
            else:
                # turn down mic volume ("down for louder backing track")
                avoladjust = f'volume={1+voladjust}'
                normfilter.append(avoladjust)
                songfilter.append('volume=1.0')
        else:
            songfilter.append('volume=1.0')
            normfilter.append('volume=1.0')

        normfilter.extend([
            'acompressor', # compress
            'dynaudnorm', # windowed-normalize (not peak)
            # alternative to dynaudnorm (sounds better but introduces vid lat)
            # 'ladspa=vlevel-ladspa:vlevel_mono',
            ])

        micstreams = [
            f"[0:a]{','.join(normfilter)}[a0a]" # normalized stream is a0a
            ]

        auxsends = []
        auxstreams = []

        if 'effect-reverb' in recording.effects:
            # probably too hall-y but #7 is verb type and #27 is "large room"
            auxsends.append('ladspa=file=tap_reverb:tap_reverb:c=c7=27')
        if 'effect-chorus' in recording.effects:
            # XXX mess around with nondefault
            auxsends.append('ladspa=file=tap_chorusflanger:tap_chorusflanger')

        for i, send in enumerate(auxsends):
            sendletter= string.ascii_lowercase[i+1]
            # from normalized stream to a new output
            auxstreams.append(f'[a0a]{send}[a0{sendletter}]')

        micstreams.extend(auxstreams)

        allfilter = [
            f"{'; '.join(micstreams)};",
            f"[1:a]{','.join(songfilter)}[a1]; "
            ]

        # render aout
        # NB: duration=shortest required in aout when no video, because ffmpeg
        # cant tell audio duration from webm container even with -shortest,
        # and mixes that include -vn become as long as the backing track

        if auxstreams:
            # effect-wet audio
            numaux = len(auxstreams)
            letters = [ string.ascii_lowercase[i+1] for i in range(numaux) ]
            p = ''.join([f'[a0{letter}]' for letter in letters ])
            final = p + f'[a1]amix=inputs={numaux+1}:duration=shortest[aout]'
            allfilter.append(final)
        else:
            # dry-but-normalized audio only
            allfilter.append(f"[a0a][a1]amix=inputs=2:duration=shortest[aout]")

        complex_filter = ' '.join(allfilter)

        ffmix.extend([
            '-filter_complex',
            complex_filter,
            '-map', '[aout]',
            '-ac', '2', # output channels, "downmix" to stereo
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

        if outfile is None:
            outfile = 'pipe:1'

        ffmix.extend([
            # https://stackoverflow.com/questions/20665982/convert-videos-to-webm-via-ffmpeg-faster
            '-cpu-used', '8', # gofast (default is 1, quality suffers)
            '-deadline', 'realtime', # gofast
            '-f', 'webm',
            f'{outfile}'
        ])

        logger.info(f'Mixing using')
        logger.info(' '.join([shlex.quote(s) for s in ffmix]))

        return ffmix
        
    def stream(self):
        ffmix = self.get_command()

        pffmix = subprocess.Popen(
            ffmix,
            shell=False,
        )

        # We can't use webm data piped from ffmpeg stdout directly to write
        # into files because the stream it produces has no duration; it must
        # write the duration it has to seek to the beginning of the stream.
        # we must use progress() to actually write the file if we want
        # to get a duration.
        while True:
            # XXX timeout
            output = pffmix.stdout.read(1<<20) # 1M in bytes
            if (not output) and (pffmix.poll() is not None):
                break
            if output:
                yield output

    def to_seconds(self, h, m, s):
        return int(h) * 3600 + int(m) * 60 + int(s) # ignore ms

    fps_re = re.compile(r' fps=\s*(\d+)')
    time_re = re.compile(r' time=(\d{2}):(\d{2}):(\d{2})')
    
    def progress(self, outfile):
        """Render recording to outfile.  Return an generator which yields a
        dict containing progress percentage each time it's called. Must be
        called to completion to prevent child process from stalling trying
        to write to its stdout.
        """
        duration = self.recording.dry_duration
        ffmix = self.get_command(outfile)
        pffmix = subprocess.Popen(
            ffmix,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1 # line buffered
        )
        current = None
        fps = 0

        while True:
            line = pffmix.stderr.readline()
            if not line:
                break
            line = line.rstrip()
            logger.info(line)
            current_result = self.time_re.search(line)
            if current_result:
                current = self.to_seconds(*current_result.groups())
                fps_result = self.fps_re.search(line)
                if fps_result:
                    try:
                        fps = int(fps_result.group(1))
                    except ValueError:
                        pass
                    
            if duration and current:
                pct = current * 100 / duration
            else:
                pct = 0

            yield {
                'pct':pct,
                'current':current,
                'duration':duration,
                'fps':fps,
            }

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
            
