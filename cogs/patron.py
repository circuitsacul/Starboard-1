import discord
import os
import dotenv
import bot_config
import json
from discord.ext import commands
from pprint import pprint

from bot_config import COLOR, SUPPORT_SERVER_ID

dotenv.load_dotenv()

DONATEBOT_TOKEN = os.getenv("DONATEBOT_TOKEN")
HOOK_AUTH = os.getenv("TOP_HOOK_AUTH")


class Premium(commands.Cog):
    """Premium related commands"""
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_patreon_event(self, text: str):
        data = json.loads(text)
        pprint(data['data'])
        return
        cents = int(data['data']['attributes']['campaign_pledge_amount_cents'])

    @commands.command(
        name='patron', aliases=['donate', 'premium'],
        description='View information on how you can donate and what the '
        'benefits are',
        brief='View donation info'
    )
    async def show_donate_info(self, ctx):
        embed = discord.Embed(color=COLOR, title='Patron/Donation Info')
        embed.description = f"Click [here]({bot_config.DONATE}) "\
            "to become a patron!\n"\
            "I really appreciate any support you can give me :)"\
            "\n\nIf you want to donate, click [here]"\
            "(https://donatebot.io/checkout/725336160112738385)"

        await ctx.send(embed=embed)

    @commands.command(
        name='patronLevel', aliases=['lvl', 'pl'],
        description='View a suers current patron status. User defaults to you',
        brief='View current patrons status'
    )
    async def show_patron_info(
        self, ctx, user: discord.Member = None
    ):
        user = user if user else ctx.message.author
        user_id = user.id
        title = f"Current Patron Levels for **{user}**:"
        string = ''

        embed = discord.Embed(
            title=title, description=string, color=bot_config.COLOR
        )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Premium(bot, bot.db))
