from discord.ext import commands


class WizzardRunningError(commands.CheckFailure):
    pass


def no_wizzard_running():
    async def predicate(ctx):
        can_run = True
        async with ctx.bot.wizzard_lock():
            if ctx.guild.id in ctx.bot.running_wizzards:
                raise WizzardRunningError(
                    "This command cannot be called while a setup"
                    " wizzard is running."
                )
        return can_run
    return commands.check(predicate)
