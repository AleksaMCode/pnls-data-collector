from sqlalchemy import event

from aggregator.core.orm._init_runtime import SessionFactory
from aggregator.core.orm.helpers import resolve_oui
from aggregator.core.orm.models import MAC


# before_flush - https://docs.sqlalchemy.org/en/21/orm/events.html#sqlalchemy.orm.SessionEvents
@event.listens_for(SessionFactory, "before_commit")
def mac_oui_resolver(session):
    for obj in session.new.union(session.dirty):
        if isinstance(obj, MAC) and obj.mac and not obj.oui:
            resolve_oui(session, obj)
