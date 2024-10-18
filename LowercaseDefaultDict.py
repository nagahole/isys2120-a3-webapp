from collections import defaultdict


class LowercaseDefaultDict(defaultdict):
    def __getitem__(self, item: str):
        return defaultdict.__getitem__(self, item.lower())

    def __setitem__(self, key: str, value):
        return defaultdict.__setitem__(self, key.lower(), value)
