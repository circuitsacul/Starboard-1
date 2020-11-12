import dbl
from discord.ext import commands, tasks

import logging
import os

TOP_TOKEN = os.getenv("TOP_TOKEN")
HOOK_AUTH = os.getenv("TOP_HOOK_AUTH")


class TopGG(commands.Cog):
    """Handles interactions with the top.gg API"""

    def __init__(self, bot):
        self.bot = bot
        self.token = TOP_TOKEN
        self.dblpy = dbl.DBLClient(
            self.bot, self.token, webhook_path='/dbl',
            webhook_auth=HOOK_AUTH, webhook_port=5000
        )

    @tasks.loop(minutes=30.0)
    async def update_stats(self):
        logger.info('Attempting to post server count')
        try:
            await self.dblpy.post_guild_count()
            logger.info(
                'Posted server count ({})'.format(self.dblpy.guild_count())
            )
        except Exception as e:
            logger.exception(
                'Failed to post server count\n'
                '{}: {}'.format(type(e).__name__, e)
            )

    @commands.Cog.listener()
    async def on_dbl_vote(self, data):
        logger.info('Received an upvote')
        print(data)


def setup(bot):
    global logger
    logger = logging.getLogger('bot')
    bot.add_cog(TopGG(bot))
