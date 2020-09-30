import discord, sys, asyncio, sys, os, asyncio, dotenv, functions, logging, traceback
import pretty_help
from discord.ext import commands
from typing import Union
#from flask.app import Flask
from pretty_help import PrettyHelp

dotenv.load_dotenv()

import bot_config
from events import starboard_events
from events import leveling

from database.database import Database
from api import post_guild_count

from events import leveling
from cogs.starboard import Starboard
from cogs.owner import Owner
from cogs.utility import Utility
from cogs.patron import PatronCommands, HttpWebHook
from cogs.levels import Levels
from cogs.settings import Settings
#from cogs.patron import FlaskWebHook

_TOKEN = os.getenv('TOKEN')
_BETA_TOKEN = os.getenv('BETA_TOKEN')

BETA = True if len(sys.argv) > 1 and sys.argv[1] == 'beta' else False
TOKEN = _BETA_TOKEN if BETA and _BETA_TOKEN is not None else _TOKEN
DB_PATH = bot_config.BETA_DB_PATH if BETA else bot_config.DB_PATH
#PREFIX = commands.when_mentioned_or(bot_config.DEFAULT_PREFIX)

db = Database(DB_PATH)

emojis = bot_config.PAGINATOR_EMOJIS
navigation = pretty_help.Navigation(page_left=emojis[0], page_right=emojis[1], remove=emojis[2])


class Bot(commands.Bot):
    def __init__(self, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db


bot = Bot(
    db, command_prefix=functions._prefix_callable,
    help_command=PrettyHelp(
        color=bot_config.COLOR, no_category="Info", active=30,
        navigation=navigation
    ),
    case_insensitive=True
)
#web_server = FlaskWebHook(bot, db)
web_server = HttpWebHook(bot, db)

#running = True


# Handle Donations
#@tasks.loop(seconds=30)
#async def _handle_donation():
#    if not running:
#        return
#    handle_donations()


#def handle_donations():
#    print("Running Donation Handler")
#    cp_queue = web_server.queue.copy()
#    for item in cp_queue:
#        print("New Donation Event")
#        print(item)

# Info Commands
@bot.command(
    name='links', aliases=['invite', 'support'],
    description='View helpful links',
    brief='View helpful links'
)
async def show_links(ctx):
    embed = discord.Embed(title="Helpful Links", color=bot_config.COLOR)
    description = \
        f"""**[Support Server]({bot_config.SUPPORT_SERVER})
        [Invite Me]({bot_config.INVITE})
        [Submit Bug Report or Suggestion]({bot_config.ISSUES_PAGE})
        [Source Code]({bot_config.SOURCE_CODE})
        [Donate/Become a Patron]({bot_config.DONATE})**
        """
    embed.description = description
    await ctx.send(embed=embed)


@bot.command(
    name='privacy', aliases=['policy'],
    description='View the bot/owners privacy policy',
    brief="View privacy policy"
)
async def show_privacy_policy(ctx):
    embed = discord.Embed(title='Privacy Policy', color=bot_config.COLOR)
    embed.description = bot_config.PRIVACY_POLICY
    await ctx.send(embed=embed)


@bot.command(
    name='about', brief='About Starboards',
    description='Give quick description of what a starboard is and what it is for'
)
async def about_starbot(ctx):
    msg = """
    Starboard is a Discord starboard bot.\
    Starboards are kind of like democratic pins.\
    A user can "vote" to have a message displayed on a channel by reacting with an emoji, usually a star.\
    A Starboard is a great way to archive funny messages.\
    """
    embed=discord.Embed(
        title='About StarBot and Starboards',
        description=msg, color=0xFCFF00
    )
    await ctx.send(embed=embed)


@bot.command(
    name='ping', aliases=['latency'], description='Get bot latency',
    brief='Get bot latency'
    )
async def ping(ctx):
    await ctx.send('Pong! {0} ms'.format(int(bot.latency*1000)))


@bot.command(name='stats', aliases=['botstats'], description='Bot stats', brief='Bot stats')
async def stats_for_bot(ctx):
    embed = discord.Embed(
        title='Bot Stats', colour=0xFCFF00,
        description = f"""
        **Guilds:** {len(bot.guilds)}
        **Users:** {len(bot.users)}
        **Ping:** {int(bot.latency*1000)} ms
        """
        )
    await ctx.send(embed=embed)


# Events
@bot.event
async def on_raw_reaction_add(payload):
    guild_id = payload.guild_id
    channel_id = payload.channel_id
    message_id = payload.message_id
    user_id = payload.user_id
    emoji = payload.emoji

    await starboard_events.handle_reaction(db, bot, guild_id, channel_id, user_id, message_id, emoji, True)


@bot.event
async def on_raw_reaction_remove(payload):
    guild_id = payload.guild_id
    channel_id = payload.channel_id
    message_id = payload.message_id
    user_id = payload.user_id
    emoji = payload.emoji

    await starboard_events.handle_reaction(db, bot, guild_id, channel_id, user_id, message_id, emoji, False)


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    elif message.content.replace('!', '') == bot.user.mention:
        conn = await db.connect()

        async with db.lock and conn.transaction():
            await functions.check_or_create_existence(
                db, conn, bot, message.guild.id, message.author,
                do_member=True
            )
        p = await functions.get_one_prefix(bot, message.guild.id)
        await message.channel.send(f"Some useful commands are `{p}help` and `{p}links`\nYou can see all my prefixes with `{p}prefixes`")
        await conn.close()
    else:
        await bot.process_commands(message)


@bot.event
async def on_error(event, *args, **kwargs):
    owner = bot.get_user(bot_config.OWNER_ID)
    await owner.send(f"Error on event {event} with args {args} and kwargs {kwargs}\n\n```{traceback.format_exc()}```")


@bot.event
async def on_command_error(ctx, error):
    if type(error) is discord.ext.commands.errors.CommandNotFound:
        return
    elif type(error) is discord.ext.commands.errors.BadArgument:
        pass
    elif type(error) is discord.ext.commands.errors.MissingRequiredArgument:
        pass
    elif type(error) is discord.ext.commands.errors.NoPrivateMessage:
        pass
    elif type(error) is discord.ext.commands.errors.MissingPermissions:
        pass
    elif type(error) is discord.ext.commands.errors.NotOwner:
        pass
    elif type(error) is discord.http.Forbidden:
        error = "I don't have the permissions to do that"
    else:
        print(f"Error {type(error)}: {error}")

        embed = discord.Embed(
            title='Error!',
            description='An unexpected error ocurred.\
                Please report this to the dev.',
            color=bot_config.ERROR_COLOR
        )
        embed.add_field(
            name='Error Message:',
            value=f"{type(error)}:\n{error}",
            inline=False
        )
        embed.add_field(
            name='Report?',
            value=f"Are you ok if I report this to the bot dev? React below with :white_check_mark: for yes.",
            inline=False
        )

        report = await functions.confirm(
            bot, ctx.channel,
            None,
            ctx.message.author.id,
            embed=embed,
            delete=False
        )
        if report:
            await ctx.send("I've reported the problem! Please still consider joining the support server and explaining what happened.")
            owner_embed = discord.Embed(
                title=f'Error in {ctx.guild.name} ({ctx.guild.id})',
                description=f"{type(error)}:\n{error}",
                color=bot_config.ERROR_COLOR
            )
            owner = bot.get_user(bot.owner_id)
            await owner.send(embed=owner_embed)
        else:
            await ctx.send("This problem was not reported. Please consider joining the support server and explaining what happened.")
        return
    embed = discord.Embed(
        title='Oops!',
        description=f"```{error}```",
        color=bot_config.MISTAKE_COLOR
    )
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Mention me for help"))
    print(f"Logged in as {bot.user.name} in {len(bot.guilds)} guilds!")


async def main():
    await db.open()
    await web_server.start()
    if not BETA:
        bot.loop.create_task(post_guild_count.loop_post(bot))

    bot.add_cog(Starboard(bot, db))
    bot.add_cog(Owner(bot, db))
    bot.add_cog(Utility(bot, db))
    bot.add_cog(PatronCommands(bot, db))
    bot.add_cog(Levels(bot, db))
    bot.add_cog(Settings(bot, db))
    await bot.start(TOKEN)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(type(e), e)
    finally:
        print("Logging out")
        loop.run_until_complete(bot.logout())
        loop.run_until_complete(web_server.close())
