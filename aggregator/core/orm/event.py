from sqlalchemy import event

from aggregator.core.orm._init_runtime import SessionFactory
from aggregator.core.orm.helpers import resolve_oui
from aggregator.core.orm.models import (
    MAC,
    ImportsWorkflow,
    WorkflowStatus,
    workflow_now,
)


# before_commit - https://docs.sqlalchemy.org/en/21/orm/events.html#sqlalchemy.orm.SessionEvents
@event.listens_for(SessionFactory, "before_commit")
def mac_oui_resolver(session):
    for obj in session.new.union(session.dirty):
        if isinstance(obj, MAC) and obj.mac and not obj.oui:
            resolve_oui(session, obj)


@event.listens_for(SessionFactory, "before_flush")
def imports_workflow_end_timestamp_setter(session, flush_context, instances):
    terminal_statuses = {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED}

    for obj in session.new.union(session.dirty):
        if (
            isinstance(obj, ImportsWorkflow)
            and not obj.end
            and obj.status in terminal_statuses
        ):
            obj.end = workflow_now()
