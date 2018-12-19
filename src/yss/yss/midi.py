import io
import sys
import struct

debug = False

# text types.
TEXT_LYRIC  = 0
TEXT_INFO   = 1
TEXT_TITLE  = 2

class MidiTimestamp:
    """ This class is used to apply the tempo changes to the click
    count, thus computing a time in milliseconds for any number of
    clicks from the beginning of the song. """

    def __init__(self, midifile):
        self.ClickUnitsPerQuarter = midifile.ClickUnitsPerQuarter
        self.Tempo = midifile.Tempo
        self.ms = 0
        self.click = 0
        self.i = 0

    def advanceToClick(self, click):
        # Moves time forward to the indicated click number.
        clicks = click - self.click
        if clicks < 0:
            # Ignore jumps backward in time.
            return

        while clicks > 0 and self.i < len(self.Tempo):
            # How many clicks remain at the current tempo?
            clicksRemaining = max(self.Tempo[self.i][0] - self.click, 0)
            clicksUsed = min(clicks, clicksRemaining)
            if clicksUsed != 0:
                self.ms += self.getTimeForClicks(clicksUsed, self.Tempo[self.i - 1][1])
            self.click += clicksUsed
            clicks -= clicksUsed
            clicksRemaining -= clicksUsed
            if clicksRemaining == 0:
                self.i += 1

        if clicks > 0:
            # We have reached the last tempo mark of the song, so this
            # tempo holds forever.
            self.ms += self.getTimeForClicks(clicks, self.Tempo[-1][1])
            self.click += clicks

    def getTimeForClicks(self, clicks, tempo):
        microseconds = ( ( float(clicks) / self.ClickUnitsPerQuarter ) * tempo );
        time_ms = microseconds / 1000
        return (time_ms)

class LyricSyllable:
    """ Each instance of this class records a single lyric event,
    e.g. a syllable of a word to be displayed and change color at a
    given time.  The Lyrics class stores a list of these. """

    def __init__(self, click, text, line, type = TEXT_LYRIC):
        self.click = click
        self.ms = None
        self.text = text
        self.line = line
        self.type = type

        # This is filled in when the syllable is drawn onscreen.
        self.left = None
        self.right = None

    def makeCopy(self, text):
        # Returns a new LyricSyllable, exactly like this one, with
        # the text replaced by the indicated string
        syllable = LyricSyllable(self.click, text, self.line, self.type)
        syllable.ms = self.ms
        return syllable

    def __repr__(self):
        return "<%s %s>" % (self.ms, self.text)

class Lyrics:
    """ This is the complete lyrics of a song, organized as a list of
    syllables sorted by event time. """

    def __init__(self):
        self.list = []
        self.line = 0

    def hasAny(self):
        # Returns true if there are any lyrics.
        return bool(self.list)

    def recordText(self, click, text):
        # Records a MIDI 0x1 text event (a syllable).

        # Make sure there are no stray null characters in the string.
        text = text.replace('\x00', '')
        # Or CR's.
        text = text.replace('\r', '')

        if not text:
            # Ignore blank lines.
            return

        if text[0] == '@':
            if text[1] == 'T':
                # A title.
                type = TEXT_TITLE
            elif text[1] == 'I':
                # An info line.
                type = TEXT_INFO
            else:
                # Any other comment we ignore.
                return

            # Put the comment onscreen.
            for line in text[2:].split('\n'):
                line = line.strip()
                self.line += 1
                self.list.append(LyricSyllable(click, line, self.line, type))
            return

        if text[0] == '\\':
            # Paragraph break.  We treat it the same as line break,
            # but with an extra blank line.
            self.line += 2
            text = text[1:]
        elif text[0] == '/':
            # Line break.
            self.line += 1
            text = text[1:]

        if text:
            lines = text.split('\n')
            self.list.append(LyricSyllable(click, lines[0], self.line))
            for line in lines[1:]:
                self.line += 1
                self.list.append(LyricSyllable(click, line, self.line))

    def recordLyric(self, click, text):
        # Records a MIDI 0x5 lyric event (a syllable).

        # Make sure there are no stray null characters in the string.
        text = text.replace('\x00', '')

        if text == '\n':
            # Paragraph break.  We treat it the same as line break,
            # but with an extra blank line.
            self.line += 2

        elif text == '\r' or text == '\r\n':
            # Line break.
            self.line += 1

        elif text:
            text = text.replace('\r', '')

            if text[0] == '\\':
                # Paragraph break.  This is a text event convention, not a
                # lyric event convention, but some midi files don't play
                # by the rules.
                self.line += 2
                text = text[1:]
            elif text[0] == '/':
                # Line break.  A text convention, but see above.
                self.line += 1
                text = text[1:]

            # Lyrics aren't supposed to include embedded newlines, but
            # sometimes they do anyway.
            lines = text.split('\n')
            self.list.append(LyricSyllable(click, lines[0], self.line))
            for line in lines[1:]:
                self.line += 1
                self.list.append(LyricSyllable(click, line, self.line))

    def computeTiming(self, midifile):
        # Walk through the lyrics and convert the click information to
        # elapsed time in milliseconds.

        ts = MidiTimestamp(midifile)
        for syllable in self.list:
            ts.advanceToClick(syllable.click)
            syllable.ms = int(ts.ms)

        # Also change the firstNoteClick to firstNoteMs, for each track.
        for track_desc in midifile.trackList:
            ts = MidiTimestamp(midifile)
            if track_desc.FirstNoteClick != None:
                ts.advanceToClick(track_desc.FirstNoteClick)
                track_desc.FirstNoteMs = ts.ms
                if debug:
                    print ("T%s first note at %s clicks, %s ms" % (
                        track_desc.TrackNum, track_desc.FirstNoteClick,
                        track_desc.FirstNoteMs))
            if track_desc.LastNoteClick != None:
                ts.advanceToClick(track_desc.LastNoteClick)
                track_desc.LastNoteMs = ts.ms

    def analyzeSpaces(self):
        """ Checks for a degenerate case: no (or very few) spaces
        between words.  Sometimes Karaoke writers omit the spaces
        between words, which makes the text very hard to read.  If we
        detect this case, repair it by adding spaces back in. """

        # First, group the syllables into lines.
        lineNumber = None
        lines = []
        currentLine = []

        for syllable in self.list:
            if syllable.line != lineNumber:
                if currentLine:
                    lines.append(currentLine)
                currentLine = []
                lineNumber = syllable.line
            currentLine.append(syllable)

        if currentLine:
            lines.append(currentLine)

        # Now, count the spaces between the syllables of the lines.
        totalNumSyls = 0
        totalNumGaps = 0
        for line in lines:
            numSyls = len(line) - 1
            numGaps = 0
            for i in range(numSyls):
                if line[i].text.rstrip() != line[i].text or \
                   line[i + 1].text.lstrip() != line[i + 1].text:
                    numGaps += 1

            totalNumSyls += numSyls
            totalNumGaps += numGaps

        if totalNumSyls and float(totalNumGaps) / float(totalNumSyls) < 0.1:
            # Too few spaces.  Insert more.
            for line in lines:
                for syllable in line[:-1]:
                    if syllable.text.endswith('-'):
                        # Assume a trailing hyphen means to join syllables.
                        syllable.text = syllable.text[:-1]
                    else:
                        syllable.text += ' '


    def wordWrapLyrics(self, font):
        # Walks through the lyrics and folds each line to the
        # indicated width.  Returns the new lyrics as a list of lists
        # of syllables; that is, each element in the returned list
        # corresponds to a displayable line, and each line is a list
        # of syllabels.

        if not self.list:
            return []

        maxWidth = 40 # manager.displaySize[0] - X_BORDER * 2

        lines = []

        x = 0
        currentLine = []
        currentText = ''
        lineNumber = self.list[0].line
        for syllable in self.list:
            # Ensure the screen position of the syllable is cleared,
            # in case we are re-wrapping text that was already
            # displayed.
            syllable.left = None
            syllable.right = None

            while lineNumber < syllable.line:
                # A newline.
                lines.append(currentLine)
                x = 0
                currentLine = []
                currentText = ''
                lineNumber += 1

            width, height = font.size(syllable.text)
            currentLine.append(syllable)
            currentText += syllable.text
            x += width
            while x > maxWidth:
                foldPoint = 80 # manager.FindFoldPoint(currentText, font, maxWidth)
                if foldPoint == len(currentText):
                    # Never mind.  Must be just whitespace on the end of
                    # the line; let it pass.
                    break

                # All the characters before foldPoint get output as the
                # first line.
                n = 0
                i = 0
                text = currentLine[i].text
                outputLine = []
                while n + len(text) <= foldPoint:
                    outputLine.append(currentLine[i])
                    n += len(text)
                    i += 1
                    text = currentLine[i].text

                syllable = currentLine[i]
                if i == 0:
                    # One long line.  Break it mid-phrase.
                    a = syllable.makeCopy(syllable.text[:foldPoint])
                    outputLine.append(a)
                    b = syllable.makeCopy('  ' + syllable.text[foldPoint:])
                    currentLine[i] = b

                else:
                    currentLine[i] = syllable.makeCopy('  ' + syllable.text)

                # The remaining characters become the next line.
                lines.append(outputLine)
                currentLine = currentLine[i:]
                currentText = ''
                for syllable in currentLine:
                    currentText += syllable.text
                x, height = font.size(currentText)

        lines.append(currentLine)

        # Indicated that the first syllable of each line is flush with
        # the left edge of the screen.
        for l in lines:
            if l:
                l[0].left = 0 # X_BORDER

        #print lines
        return lines

    def write(self):
        # Outputs the lyrics, one line at a time.
        for syllable in self.list:
            print ("%s(%s) %s %s" % (syllable.ms, syllable.click, syllable.line, repr(syllable.text)))

# Read a variable length quantity from the file's current read position.
# Reads the file one byte at a time until the full value has been read,
# and returns a tuple of the full integer and the number of bytes read
def varLength(filehdl):
    convertedInt = 0
    bitShift = 0
    bytesRead = 0
    while (bitShift <= 42):
        byteStr = filehdl.read(1)
        bytesRead = bytesRead + 1
        if byteStr:
            byteVal = ord(byteStr)
            convertedInt = (convertedInt << 7) | (byteVal & 0x7F)
            #print ("<0x%X/0x%X>"% (byteVal, convertedInt))
            if (byteVal & 0x80):
                bitShift = bitShift + 7
            else:
                break
        else:
            return (0, 0)
    return (convertedInt, bytesRead)

def midiProcessEvent (filehdl, track_desc, midifile, ErrorNotifyCallback):
    bytesRead = 0
    click, varBytes = varLength(filehdl)
    if varBytes == 0:
        return 0
    bytesRead = bytesRead + varBytes
    track_desc.TotalClicksFromStart += click
    byteStr = filehdl.read(1)
    bytesRead = bytesRead + 1
    status_byte = ord(byteStr)

    # Handle the MIDI running status. This allows consecutive
    # commands of the same event type to not bother sending
    # the event type again. If the top bit isn't set it's a
    # data byte using the last event type.
    if (status_byte & 0x80):
        # This is a new status byte, not a data byte using
        # the running status. Set the current running status
        # to this new status byte and use it as the event type.
        event_type = status_byte
        # Only save running status for voice messages
        if (event_type & 0xF0) != 0xF0:
            track_desc.RunningStatus = event_type

    else:
        # Use the last event type, and seek back in the file
        # as this byte is actual data, not an event code
        event_type = track_desc.RunningStatus
        filehdl.seek (-1, 1)
        bytesRead = bytesRead - 1

    #print ("T%d: VarBytes = %d, event_type = 0x%X" % (track_desc.TrackNum, varBytes, event_type))
##     if debug:
##         print "Event: 0x%X" % event_type

    # Handle all event types
    if event_type == 0xFF:
        byteStr = filehdl.read(1)
        bytesRead = bytesRead + 1
        event = ord(byteStr)
        if debug:
            print ("MetaEvent: 0x%X" % event)
        if event == 0x00:
            # Sequence number (discarded)
            packet = filehdl.read(2)
            bytesRead = bytesRead + 2
            zero, type = unpack_packet(packet)
            if type == 0x02:
                # Discard next two bytes as well
                filehdl.read(2)
            elif type == 0x00:
                # Nothing left to discard
                pass
            else:
                if debug:
                    print ("Invalid sequence number (%d)" % type)
        elif event == 0x01:
            # Text Event
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            text = filehdl.read(Length)
            bytesRead = bytesRead + Length
            if Length > 1000:
                # This must be a mistake.
                if debug:
                    print ("Ignoring text of length %s" % (Length))
            else:
                if not midifile.text_encoding:
                    text = text.decode('utf-8', 'replace')
                else:
                    text = text.decode(midifile.text_encoding, 'replace')
                # Take out any Sysex text events, and append to the lyrics list
                if (" SYX" not in text) and ("Track-" not in text) \
                    and ("%-" not in text) and ("%+" not in text):
                    track_desc.text_events.recordText(track_desc.TotalClicksFromStart, text)
                if debug:
                    print ("Text: %s" % (repr(text)))
        elif event == 0x02:
            # Copyright (discard)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length
        elif event == 0x03:
            # Title of track
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            title = filehdl.read(Length)
            bytesRead = bytesRead + Length
            if debug:
                print ("Track Title: " + repr(title))
            if title == "Words":
                track_desc.LyricsTrack = True
        elif event == 0x04:
            # Instrument (discard)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length
        elif event == 0x05:
            # Lyric Event (a new style text record)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            lyric = filehdl.read(Length)
            if not midifile.text_encoding:
                lyric = lyric.decode('utf-8', 'replace')
            else:
                lyric = lyric.decode(midifile.text_encoding, 'replace')
            bytesRead = bytesRead + Length
            # Take out any Sysex text events, and append to the lyrics list
            if (" SYX" not in lyric) and ("Track-" not in lyric) \
                and ("%-" not in lyric) and ("%+" not in lyric):
                track_desc.lyric_events.recordLyric(track_desc.TotalClicksFromStart, lyric)
            if debug:
                print ("Lyric: %s" % (repr(lyric)))
        elif event == 0x06:
            # Marker (discard)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length
        elif event == 0x07:
            # Cue point (discard)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length
        elif event == 0x08:
            # Program name (discard)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length
        elif event == 0x09:
            # Device (port) name (discard)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length
        elif event == 0x20:
            # MIDI Channel (discard)
            packet = filehdl.read(2)
            bytesRead = bytesRead + 2
        elif event == 0x21:
            # MIDI Port (discard)
            packet = filehdl.read(2)
            bytesRead = bytesRead + 2
        elif event == 0x2F:
            # End of track
            byteStr = filehdl.read(1)
            bytesRead = bytesRead + 1
            valid = ord(byteStr)
            if valid != 0:
                print ("Invalid End of track")
        elif event == 0x51:
            # Set Tempo
            packet = filehdl.read(4)
            bytesRead = bytesRead + 4
            valid, tempoA, tempoB, tempoC = unpack_packet(packet)
            if valid != 0x03:
                print ("Error: Invalid tempo")
            tempo = (tempoA << 16) | (tempoB << 8) | tempoC
            midifile.Tempo.append((track_desc.TotalClicksFromStart, tempo))
            if debug:
                ms_per_quarter = (tempo/1000)
                print ("Tempo: %d (%d ms per quarter note)"% (tempo, ms_per_quarter))
        elif event == 0x54:
            # SMPTE (discard)
            packet = filehdl.read(6)
            bytesRead = bytesRead + 6
        elif event == 0x58:
            # Meta Event: Time Signature
            packet = filehdl.read(5)
            bytesRead = bytesRead + 5
            valid, num, denom, clocks, notes = unpack_packet(packet)
            if valid != 0x04:
                print ("Error: Invalid time signature (valid=%d, num=%d, denom=%d)" % (valid,num,denom))
            midifile.Numerator = num
            midifile.Denominator = denom
            midifile.ClocksPerMetronomeTick = clocks
            midifile.NotesPer24MIDIClocks = notes
        elif event == 0x59:
            # Key signature (discard)
            packet = filehdl.read(3)
            bytesRead = bytesRead + 3
            valid, sf, mi = unpack_packet(packet)
            if valid != 0x02:
                print ("Error: Invalid key signature (valid=%d, sf=%d, mi=%d)" % (valid,sf,mi))
        elif event == 0x7F:
            # Sequencer Specific Meta Event
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            byteStr = filehdl.read(1)
            bytesRead = bytesRead + 1
            ID = ord(byteStr)
            if ID == 0:
                packet = filehdl.read(2)
                bytesRead = bytesRead + 2
                ID = struct.unpack('>H', packet)[0]
                Length = Length - 3
            else:
                Length = Length - 1
            data = filehdl.read(Length)
            bytesRead = bytesRead + Length
            if debug:
                print ("Sequencer Specific Event (Data Length %d)"%Length)
                print ("Manufacturer's ID: " + str(ID))
                print ("Manufacturer Data: " + data)
        else:
            # Unknown event (discard)
            if debug:
                print ("Unknown meta-event: 0x%X" % event)
            Length, varBytes = varLength(filehdl)
            bytesRead = bytesRead + varBytes
            filehdl.read(Length) # discard
            bytesRead = bytesRead + Length

    elif (event_type & 0xF0) == 0x80:
        # Note off
        packet = filehdl.read(2)
        bytesRead = bytesRead + 2
        track_desc.LastNoteClick = track_desc.TotalClicksFromStart
    elif (event_type & 0xF0) == 0x90:
        # Note on (discard but note if the start time of the first in the track)
        packet = filehdl.read(2)
        bytesRead = bytesRead + 2
        #print ("T%d: 0x%X" % (track_desc.TrackNum, event_type))
        if track_desc.FirstNoteClick == None:
            track_desc.FirstNoteClick = track_desc.TotalClicksFromStart
        track_desc.LastNoteClick = track_desc.TotalClicksFromStart
    elif (event_type & 0xF0) == 0xA0:
        # Key after-touch (discard)
        packet = filehdl.read(2)
        bytesRead = bytesRead + 2
    elif (event_type & 0xF0) == 0xB0:
        # Control change (discard)
        packet = filehdl.read(2)
        bytesRead = bytesRead + 2
        if debug:
            c, v = unpack_packet(packet)
            print ("Control: C%d V%d" % (c,v))
    elif (event_type & 0xF0) == 0xC0:
        # Program (patch) change (discard)
        packet = filehdl.read(1)
        bytesRead = bytesRead + 1
    elif (event_type & 0xF0) == 0xD0:
        # Channel after-touch (discard)
        packet = filehdl.read(1)
        bytesRead = bytesRead + 1
    elif (event_type & 0xF0) == 0xE0:
        # Pitch wheel change (discard)
        packet = filehdl.read(2)
        bytesRead = bytesRead + 2
    elif event_type == 0xF0:
        # F0 Sysex Event (discard)
        Length, varBytes = varLength(filehdl)
        bytesRead = bytesRead + varBytes
        filehdl.read(Length - 1) # discard
        end_byte = filehdl.read(1)
        end = ord(end_byte)
        bytesRead = bytesRead + Length
        if (end != 0xF7):
            print ("Invalid F0 Sysex end byte (0x%X)" % end)
    elif event_type == 0xF7:
        # F7 Sysex Event (discard)
        Length, varBytes = varLength(filehdl)
        bytesRead = bytesRead + varBytes
        filehdl.read(Length) # discard
        bytesRead = bytesRead + Length
    else:
        # Unknown event (discard)
        if debug:
            print ("Unknown event: 0x%x" % event_type)
        Length, varBytes = varLength(filehdl)
        bytesRead = bytesRead + varBytes
        filehdl.read(Length) # discard
        bytesRead = bytesRead + Length
    return bytesRead

def midiParseTrack (filehdl, midifile, trackNum, Length, ErrorNotifyCallback):
    # Create the new TrackDesc structure
    track = TrackDesc(trackNum)
    if debug:
        print("Track %d" % trackNum)
    # Loop through all events in the track, recording salient meta-events and times
    eventBytes = 0
    while track.BytesRead < Length:
        eventBytes = midiProcessEvent(filehdl, track, midifile, ErrorNotifyCallback)
        if (eventBytes == None) or (eventBytes == -1) or (eventBytes == 0):
            return None
        track.BytesRead = track.BytesRead + eventBytes
    return track

class midiFile:
    def __init__(self):
        self.trackList = []         # List of TrackDesc track descriptors

        # Chosen lyric list from above.  It is converted by
        # computeTiming() from a list of (clicks, text) into a list of
        # (ms, text).
        self.lyrics = []

        # self.text_encoding = "iso-8859-13"
        self.text_encoding = ""      # The encoding of text in midi file

        self.ClickUnitsPerSMPTE = None
        self.SMPTEFramesPerSec = None
        self.ClickUnitsPerQuarter = None

        # The tempo of the song may change throughout, so we have to
        # record the click at which each tempo change occurred, and
        # the new tempo at that point.  Then, after we have read in
        # all the tracks (and thus collected all the tempo changes),
        # we can go back and apply this knowledge to the other tracks.
        self.Tempo = [(0, 0)]

        self.Numerator = None               # Numerator
        self.Denominator = None             # Denominator
        self.ClocksPerMetronomeTick = None  # MIDI clocks per metronome tick
        self.NotesPer24MIDIClocks = None    # 1/32 Notes per 24 MIDI clocks
        self.earliestNoteMS = 0             # Start of earliest note in song
        self.lastNoteMS = 0                 # End of latest note in song


class TrackDesc:
    def __init__(self, trackNum):
        self.TrackNum = trackNum        # Track number
        self.TotalClicksFromStart = 0   # Store number of clicks elapsed from start
        self.BytesRead = 0              # Number of file bytes read for track
        self.FirstNoteClick = None      # Start of first note in track
        self.FirstNoteMs = None         # The same, in milliseconds
        self.LastNoteClick = None       # End of last note in track
        self.LastNoteMs = None          # In millseconds
        self.LyricsTrack = False        # This track contains lyrics
        self.RunningStatus = 0          # MIDI Running Status byte

        self.text_events = Lyrics()       # Lyrics (0x1 events)
        self.lyric_events = Lyrics()      # Lyrics (0x5 events)

def midiParseData(midiData, ErrorNotifyCallback, Encoding):

    # Create the midiFile structure
    midifile = midiFile()
    midifile.text_encoding = Encoding

    # Open the file
    filehdl = io.BytesIO(midiData)

    # Check it's a MThd chunk
    packet = filehdl.read(8)
    ChunkType, Length = struct.unpack('>4sL', packet)
    if (ChunkType != b"MThd"):
        ErrorNotifyCallback ("No MIDI Header chunk at start")
        return None

    # Read header
    packet = filehdl.read(Length)
    format, tracks, division = struct.unpack('>HHH', packet)
    if (division & 0x8000):
        midifile.ClickUnitsPerSMPTE = division & 0x00FF
        midifile.SMPTEFramesPerSec = division & 0x7F00
    else:
        midifile.ClickUnitsPerQuarter = division & 0x7FFF

    # Loop through parsing all tracks
    trackBytes = 1
    trackNum = 0
    while (trackBytes != 0):
        # Read the next track header
        packet = filehdl.read(8)
        if packet == "" or len(packet) < 8:
            # End of file, we're leaving
            break
        # Check it's a MTrk
        ChunkType, Length = struct.unpack('>4sL', packet)
        if (ChunkType != b"MTrk"):
            if debug:
                print ("Didn't find expected MIDI Track")

        # Process the track, getting a TrackDesc structure
        track_desc = midiParseTrack(filehdl, midifile, trackNum, Length, ErrorNotifyCallback)
        if track_desc:
            trackBytes = track_desc.BytesRead
            # Store the track descriptor with the others
            midifile.trackList.append(track_desc)
            # Debug out the first note for this track
            if debug:
                print ("T%d: First note(%s)" % (trackNum, track_desc.FirstNoteClick))
            trackNum = trackNum + 1

    # Close the open file
    filehdl.close()

    # Get the lyrics from the best track.  We prefer any tracks that
    # are "lyrics" tracks.  Failing that, we get the track with the
    # most number of syllables.
    bestSortKey = ()
    midifile.lyrics = None

    for track_desc in midifile.trackList:
        lyrics = None

        # Decide which list of lyric events to choose. There may be
        # text events (0x01), lyric events (0x05) or sometimes both
        # for compatibility. If both are available, we choose the one
        # with the most syllables, or text if they're the same.
        if track_desc.text_events.hasAny() and track_desc.lyric_events.hasAny():
            if len(track_desc.lyric_events.list) > len(track_desc.text_events.list):
                lyrics = track_desc.lyric_events
            else:
                lyrics = track_desc.text_events
        elif track_desc.text_events.hasAny():
            lyrics = track_desc.text_events
        elif track_desc.lyric_events.hasAny():
            lyrics = track_desc.lyric_events

        if not lyrics:
            continue
        sortKey = (track_desc.LyricsTrack, len(lyrics.list))
        if sortKey > bestSortKey:
            bestSortKey = sortKey
            midifile.lyrics = lyrics

    if not midifile.lyrics:
        ErrorNotifyCallback ("No lyrics in the track")
        return None

    midifile.lyrics.computeTiming(midifile)
    midifile.lyrics.analyzeSpaces()

    # Calculate the song start (earliest note event in all tracks), as
    # well as the song end (last note event in all tracks).
    earliestNoteMS = None
    lastNoteMS = None
    for track in midifile.trackList:
        if track.FirstNoteMs != None:
            if (earliestNoteMS == None) or (track.FirstNoteMs < earliestNoteMS):
                earliestNoteMS = track.FirstNoteMs
        if track.LastNoteMs != None:
            if (lastNoteMS == None) or (track.LastNoteMs > lastNoteMS):
                lastNoteMS = track.LastNoteMs
    midifile.earliestNoteMS = earliestNoteMS
    midifile.lastNoteMS = lastNoteMS

    if debug:
        print("first = %s" % (midifile.earliestNoteMS))
        print("last = %s" % (midifile.lastNoteMS))

    # Return the populated midiFile structure
    return midifile

def unpack_packet(packet):
    if sys.version_info[0] >= 3:
        return list(packet)
    else:
        return map(ord, packet)
