import discord
from paginators import disputils
from discord.ext import commands


pages = {
    'About Starboard': (
        "Starboards are like democratic pins. "
        "A user can vote to pin a message by "
        "reacting to it with :star:, and after "
        "reaching a certain number of stars "
        "it is sent to the starboard. "
        "\n\nTo setup Starboard, run `sb!setup`. "
    ), 'Starboard Settings': (
        "**requiredStars:**\nHow many stars are "
        "needed for a message to appear on the "
        "starboard.\n\n"
        "**requiredToLose:**\nHow few stars are "
        "needed before a message is removed from "
        "the starboard.\n\n"
        "**selfStar:**\nWether or not a user "
        "can star their own messages.\n\n"
        "**linkEdits:**\nIf the original message "
        "is edited, should the starboard message "
        "also be edited.\n\n"
        "**linkDeletes:**\nIf the original message "
        "is deleted, should the starboard message "
        "also be deleted.\n\n"
        "**botsOnStarboard:**\nWether or not bot "
        "messages can be sent to the starboard."
    )
}


class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name='help', aliases=['h', '?'],
        description='Get help with the bot',
        brief='Get help with the bot'
    )
    async def help_command(self, ctx):
        embeds = [
            discord.Embed(
                title=t,
                description=d
            ) for t, d in pages.items()
        ]
        p = disputils.EmbedPaginator(
            self.bot, pages=embeds
        )
        await p.run([ctx.message.author], ctx.channel)


def setup(bot):
    bot.add_cog(HelpCommand(bot))
