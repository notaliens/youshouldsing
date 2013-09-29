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

class CreatorToSong(ReferenceType):
    """ A reference type which maps creator to song """

class PerformerToUser(ReferenceType):
    """ Map a performer to the corresponding user object.
    """

class RecordingToPerformer(ReferenceType):
    pass

class RecordingToSong(ReferenceType):
    pass
