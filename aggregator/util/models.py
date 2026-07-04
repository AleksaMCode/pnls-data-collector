from enum import Enum


class AggregateWorkflowStatus(Enum):
    ACCEPTED = "ACCEPTED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"