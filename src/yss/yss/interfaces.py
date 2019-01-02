from zope.interface import Interface

from substanced.interfaces import ReferenceType
from substanced.objectmap import Cascading
from substanced.property import PropertySheet
from substanced.schema import MultireferenceIdSchemaNode
from substanced.schema import Schema
from substanced.util import get_oid

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
    # delete recordings when their associated songs are deleted
    target_integrity = Cascading.DELETE

def performers_choices(context, request):
    performers = request.virtual_root.get('performers')
    if performers is None:
        return () # fbo dump/load
    values = [(get_oid(performer), name) for name, performer in
                performers.items()]
    return values

class RelatedSchema(Schema):
    liked_by_ids = MultireferenceIdSchemaNode(
        choices_getter=performers_choices,
        title='Liked By',
        )

class RelatedPropertySheet(PropertySheet):
    schema = RelatedSchema()

sex_choices = (
    ('', '- Select -'),
    ('Female', 'Female'),
    ('Male', 'Male'),
    ('Nonbinary', 'Nonbinary'),
)

genre_choices = (
    ('', '- Select -'),
    ('Unknown', 'Unknown'),
    ('Rock', 'Rock'),
    ('Pop', 'Pop'),
    ('Country', 'Country'),
    ('Jazz', 'Jazz'),
    ('Blues', 'Blues'),
)

# for use with speech recognition, see https://cloud.google.com/speech-to-text/docs/languages
_languages = """
English en-US
French fr-FR
German de-DE
Danish da-DK
Czech cs-CZ
Catalan ca-ES
Spanish es-ES
Basque eu-ES
Italian it-IT
Latvian lv-LV
Hungarian hu-HU
Dutch nl-NL
Polish pl-PL
Portugese pt-PT
Slovak sk-SK
Slovenian sk-SK
Romanian ro-RO
Japanese ja-JP
Mandarin cmn-Hans-CN
Cantonese yue-Hant-HK
Hindi hi-IN
Arabic ar-EG
Thai th-TH
Korean ko-KR
Russian ru-RU
Bulgarian bg-BG
Greek el-GR
Armenian hy-AM
Indonesian id-ID
Malay ms-MY
Bengali bn-IN
Catalan ca-ES
Filipino fil-PH
Javanese jv-ID
Khmer km-KH
Finnish fi-FI
Swedish sv-SE
Vietnamese vi-VN
Turkish tr-TR
Urdu ur-PK
Hebrew he-IL
Ukrainian uk-UA
"""

languages = []
for lang in _languages.split('\n'):
    lang = lang.strip()
    if not lang:
        continue
    name, code = lang.split(' ', 1)
    languages.append({'name':name, 'code':code})

language_choices = [
    ('', '- Select -'),
    ]
for language in languages:
    language_choices.append((language['code'], language['name']))
