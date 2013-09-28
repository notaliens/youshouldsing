from zope.interface import Interface

class ISongs(Interface):
    """ Marker interface for the songs folder """

class IRecordings(Interface):
    """ Marker interface for the recordings folder """
    
class IPerformers(Interface):
    """ Marker interface for the performers folder """
