import discord
import sys
import asyncio
import os
from discord.errors import Forbidden
from discord.ext.commands import errors
import dotenv
from bot_config import SUPPORT_SERVER
import functions
import traceback
import pretty_help
import errors as cerrors
from discord.ext import commands
from asyncio import Lock

dotenv.load_dotenv()

import bot_config
from events import starboard_events

from database.database import Database
from api import post_guild_count

from cogs.webhook import HttpWebHook

_TOKEN = os.getenv('TOKEN')
_BETA_TOKEN = os.getenv('BETA_TOKEN')

BETA = True if len(sys.argv) > 1 and sys.argv[1] == 'beta' else False
TOKEN = _BETA_TOKEN if BETA and _BETA_TOKEN is not None else _TOKEN
BOT_DESCRIPTION = """
An advanced starboard that allows for multiple starboards and multiple emojis per starboard.
To get started, run the "setup" command.
If you need help, just mention me for a link to the support server.
"""

db = Database()

emojis = bot_config.PAGINATOR_EMOJIS
navigation = pretty_help.Navigation(
    page_left=emojis[0], page_right=emojis[1], remove=emojis[2]
)

intents = discord.Intents(
    messages=True, guilds=True, reactions=True,
    emojis=True
)


class Bot(commands.AutoShardedBot):
    def __init__(self, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db
        self.wizzard_lock = Lock


help_command = pretty_help.PrettyHelp(
    color=bot_config.COLOR,
    command_attrs={
        "name": "commands",
        'hidden': True
    }
)


bot = Bot(
    db, command_prefix=functions._prefix_callable,
    case_insensitive=True,
    intents=intents,
    help_command=help_command,
    description=BOT_DESCRIPTION
)
web_server = HttpWebHook(bot, db)


# Load Cache
async def load_aschannels(bot):
    check_aschannel = \
        """SELECT * FROM aschannels"""

    async with bot.db.lock:
        async with bot.db.conn.transaction():
            asc = await bot.db.conn.fetch(
                check_aschannel
            )

    if asc != []:
        bot.db.as_cache = set([int(a['id']) for a in asc])
    else:
        bot.db.as_cache = set()


# Events
@bot.event
async def on_guild_join(guild):
    support_server = bot.get_guild(
        bot_config.SUPPORT_SERVER_ID
    )
    log_channel = discord.utils.get(
        support_server.channels,
        id=bot_config.SERVER_LOG_ID
    )

    members = guild.member_count
    total = sum([g.member_count for g in bot.guilds])

    embed = discord.Embed(
        description=f"Joined **{guild.name}**!\n"
        f"**{members}** Members",
        color=bot_config.GUILD_JOIN_COLOR
    )
    embed.set_footer(
        text=f"We now have {len(bot.guilds)} servers and "
        f"{total} users"
    )

    await log_channel.send(embed=embed)


@bot.event
async def on_guild_remove(guild):
    support_server = bot.get_guild(
        bot_config.SUPPORT_SERVER_ID
    )
    log_channel = discord.utils.get(
        support_server.channels,
        id=bot_config.SERVER_LOG_ID
    )

    total = sum([g.member_count for g in bot.guilds])

    embed = discord.Embed(
        description=f"Left **{guild.name}**.",
        color=bot_config.GUILD_LEAVE_COLOR
    )
    embed.set_footer(
        text=f"We now have {len(bot.guilds)} servers and "
        f"{total} users"
    )

    await log_channel.send(embed=embed)


@bot.event
async def on_raw_reaction_add(payload):
    guild_id = payload.guild_id
    if guild_id is None:
        return
    channel_id = payload.channel_id
    message_id = payload.message_id
    user_id = payload.user_id
    emoji = payload.emoji

    emoji_name = str(emoji.id) if emoji.id is not None\
        else emoji.name

    if not await functions.is_starboard_emoji(
        bot.db, guild_id, emoji_name
    ):
        return

    await starboard_events.handle_reaction(
        db, bot, guild_id, channel_id,
        user_id, message_id, emoji, True
    )


@bot.event
async def on_raw_reaction_remove(payload):
    guild_id = payload.guild_id
    if guild_id is None:
        return
    channel_id = payload.channel_id
    message_id = payload.message_id
    user_id = payload.user_id
    emoji = payload.emoji

    emoji_name = emoji.id if emoji.id is not None\
        else emoji.name

    if not await functions.is_starboard_emoji(
        bot.db, guild_id, emoji_name
    ):
        return

    await starboard_events.handle_reaction(
        db, bot, guild_id, channel_id,
        user_id, message_id, emoji, False
    )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    elif message.content.replace('!', '') == bot.user.mention:
        if message.guild is not None:
            await functions.check_or_create_existence(
                bot, message.guild.id, message.author,
                do_member=True
            )

        if message.guild is not None:
            p = await functions.get_one_prefix(bot, message.guild.id)
        else:
            p = bot_config.DEFAULT_PREFIX
        try:
            await message.channel.send(
                f"To get started, run `{p}setup`.\n"
                f"To see all my commands, run `{p}help`\n"
                "If you need help, you can join the support "
                f"server {SUPPORT_SERVER}"
            )
        except Exception:
            pass
    else:
        await bot.process_commands(message)


@bot.event
async def on_error(event, *args, **kwargs):
    owner = bot.get_user(bot_config.OWNER_ID)
    await owner.send(
        f"Error on event {event} with args {args} and \
            kwargs {kwargs}\n\n```{traceback.format_exc()}```"
    )


@bot.event
async def on_command_error(ctx, error):
    try:
        error = error.original
    except Exception:
        pass
    if type(error) is discord.ext.commands.errors.CommandNotFound:
        return
    elif type(error) in [
        cerrors.BotNeedsPerms, cerrors.DoesNotExist, cerrors.NoPremiumError,
        cerrors.AlreadyExists, cerrors.InvalidArgument,
        cerrors.NotEnoughCredits
    ]:
        pass
    elif type(error) in [
        errors.BadArgument, errors.MissingRequiredArgument,
        errors.NoPrivateMessage, errors.MissingPermissions,
        errors.NotOwner, errors.CommandOnCooldown,
        errors.ChannelNotFound, errors.BadUnionArgument,
        errors.BotMissingPermissions, errors.UserNotFound
    ]:
        pass
    elif type(error) is ValueError:
        pass
    elif type(error) is Forbidden:
        error = "I don't have the permissions to do that!"
    elif type(error) is discord.http.Forbidden:
        error = "I don't have the permissions to do that!"
    else:
        print(f"Error {type(error)}: {error}")
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )

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
            value="Are you ok if I report this to the bot dev? React below \
                with :white_check_mark: for yes.",
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
            await ctx.send(
                "I've reported the problem! Please still"
                "consider joining the support server and explaining"
                "what happened."
            )
            owner_embed = discord.Embed(
                title=f'Error in {ctx.guild.name} ({ctx.guild.id})',
                description=f"{type(error)}:\n{error}",
                color=bot_config.ERROR_COLOR
            )
            owner = bot.get_user(bot_config.OWNER_ID)
            await owner.send(embed=owner_embed)
        else:
            await ctx.send(
                "This problem was not reported. Please consider "
                "joining the support server and explaining what happened."
            )
    try:
        await ctx.send(f"{error}")
    except discord.errors.Forbidden:
        await ctx.message.author.send(
            "I don't have permission to send messages in "
            f"{ctx.channel.mention}, so I can't respond "
            "to your command!"
        )


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game("Mention me for help"))
    print(f"Logged in as {bot.user.name} in {len(bot.guilds)} guilds!")


async def main():
    await db.open(bot)

    await load_aschannels(bot)

    await web_server.start()
    if not BETA:
        bot.loop.create_task(post_guild_count.loop_post(bot))

    extensions = [
        'cogs.aschannels',
        'cogs.levels',
        'cogs.owner',
        'cogs.premium',
        'cogs.settings',
        'cogs.starboard',
        'cogs.stats',
        'cogs.utility',
        'cogs.voting',
        'cogs.rand_messages',
        'cogs.info'
    ]

    for ext in extensions:
        bot.load_extension(ext)

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
        exit(1)
