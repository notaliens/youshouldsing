import datetime
import pytz

from substanced.event import subscribe_will_be_added

@subscribe_will_be_added()
def content_will_be_added(event):
    event.object.created = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
