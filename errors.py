from discord.ext.commands.errors import CheckFailure


class NoPremiumError(CheckFailure):
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
