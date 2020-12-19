class NoPremiumError(Exception):
    pass


class AlreadyExists(Exception):
    pass


class DoesNotExist(Exception):
    pass


class BotNeedsPerms(Exception):
    pass


class InvalidArgument(Exception):
    pass


class NotEnoughCredits(Exception):
    pass
