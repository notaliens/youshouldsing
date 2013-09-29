from zope.interface import Interface

from substanced.interfaces import ReferenceType

class ISongs(Interface):
    """ Marker interface for the songs folder """

class ISong(Interface):
    """ Marker interface for songs """

class IRecordings(Interface):
    """ Marker interface for the recordings folder """

class IRecording(Interface):
    """ Marker interface for recordings """

class IPerformers(Interface):
    """ Marker interface for the performers folder """

class IPerformer(Interface):
    """ Marker interface for an individual performer folder """

class PerformerLikesPerformer(ReferenceType):
    """ Map a "like" from a performer to another performer.
    """
    target_ordered = True

class PerformerLikesRecording(ReferenceType):
    """ Map a "like" from a performer to a recording.
    """
    target_ordered = True

class PerformerLikesSong(ReferenceType):
    """ Map a "like" from a performer to a song.
    """
    target_ordered = True

class PerformerToUser(ReferenceType):
    """ Map a performer to the corresponding user object.
    """

class RecordingToPerformer(ReferenceType):
    """ Map a recording to the corresponding performer.
    """
    source_ordered = True

class RecordingToSong(ReferenceType):
    """ Map a recording to the corresponding song.
    """
    source_ordered = True
