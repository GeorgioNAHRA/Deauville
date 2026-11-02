class FestivalError(Exception):
    pass


class InvalidValueError(FestivalError):
    pass


class NotFoundError(FestivalError):
    pass


class ConflictError(FestivalError):
    pass


class StorageError(FestivalError):
    pass
