from enum import Enum


class Filters(Enum):
    EQUALS = "="
    LESS_THAN = "<"
    GREATER_THAN = ">"
    NOT_EQUAL_TO = "<>"
    REGEX = "~"
    LIKE = "LIKE"
