import discord, functions
from discord.embeds import Embed
from discord.ext import commands
from typing import Union


async def change_starboard_settings(
    db, starboard_id, self_star=None, link_edits=None,
    link_deletes=None, bots_react=None, bots_on_sb=None,
    required=None, rtl=None
):
#async def change_starboard_setting(db, starboard_id, setting, value):
    get_starboard = \
        """SELECT * FROM starboards WHERE id=?"""
    update_starboard = \
        """UPDATE starboards
        SET self_star=?,
        link_edits=?,
        link_deletes=?,
        bots_react=?,
        bots_on_sb=?,
        required=?,
        rtl=?
        WHERE id=?"""

#    values = {
#        'selfstar': 'self_star',
#        'linkedits': 'link_edits',
#        'linkdeletes': 'link_deletes',
#        'botsreact': 'bots_react',
#        'botsonsb': 'bots_on_sb',
#        'required': 'required',
#        'requiredtolose': 'rtl'
#    }

    async with db.lock:
        curr = db.cursor()
        rows = curr.execute(get_starboard, [starboard_id]).fetchall()
        if len(rows) == 0:
            return None
        ssb = rows[0]

        s = {}
        s['ss'] = self_star if self_star is not None else ssb['self_star']
        s['le'] = link_edits if link_edits is not None else ssb['link_edits']
        s['ld'] = link_deletes if link_deletes is not None else ssb['link_deletes']
        s['br'] = bots_react if bots_react is not None else ssb['bots_react']
        s['bos'] = bots_on_sb if bots_on_sb is not None else ssb['bots_on_sb']
        s['r'] = required if required is not None else ssb['required']
        s['rtl'] = rtl if rtl is not None else ssb['rtl']

        try:
            curr.execute(update_starboard, [
                s['ss'], s['le'], s['ld'], s['br'], s['bos'], s['r'], s['rtl'],
                starboard_id
            ])
        except Exception as e:
            print(e)
            return False
        curr.close()
    return True


class Starboard(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='starboards', aliases=['boards', 'b', 's'],
        description='List all the starboars for this server',
        brief='List starboards'
    )
    @commands.guild_only()
    async def list_starboards(self, ctx):
        curr = self.db.cursor()
        async with self.db.lock:
            _ = functions.check_or_create_existence(self.db, curr, self.bot, guild_id=ctx.guild.id, user_id=ctx.message.author.id, do_member=True)
            get_starboards = """SELECT * FROM starboards WHERE guild_id=?"""
            curr.execute(get_starboards, (ctx.guild.id,))
            rows = curr.fetchall()
            curr.close()
        if len(rows) == 0:
            await ctx.send("You don't have any starboards")
        else:
            msg = f'Starboards: {len(rows)}\n'
            for row in rows:
                msg += f"--<#{row['id']}>\n"
            await ctx.send(msg)

    @commands.command(
        name='add', aliases=['a'],
        description='Add a starboard',
        brief='Add a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def add_starboard(self, ctx, starboard: discord.TextChannel):
        curr = self.db.cursor()
        async with self.db.lock:
            existed = functions.check_or_create_existence(self.db, curr, self.bot, guild_id=ctx.guild.id, starboard_id=starboard.id, user_id=ctx.message.author.id, do_member=True)
        if existed['se'] == True:
            await ctx.send("That is already a starboard!")
        else:
            await ctx.send(f"Added starboard {starboard.mention}")

    @commands.command(
        name='remove', aliases=['r'],
        description='Remove a starboard',
        brief='Remove a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def remove_starboard(self, ctx, starboard: discord.TextChannel):
        curr = self.db.cursor()
        async with self.db.lock:
            functions.check_or_create_existence(self.db, curr, self.bot, guild_id=ctx.guild.id, user_id=ctx.message.author.id, do_member=True)
            existed = functions.check_or_create_existence(self.db, curr, self.bot, starboard_id=starboard.id, guild_id=ctx.guild.id, create_new=False)
            if existed['se'] == False:
                await ctx.send("That is not a starboard!")
                return
            remove_starboard = """DELETE FROM starboards WHERE id=?"""
            curr.execute(remove_starboard, (starboard.id,))
        await ctx.send("Removed starboard")

    @commands.command(
        name='addEmoji', aliases=['addemoji', 'ae'],
        description='Add emoji to a starboard',
        brief='Add emoji to starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def add_starboard_emoji(self, ctx, starboard: discord.TextChannel, emoji: Union[discord.Emoji, str]):
        check_sbemoji = \
            """SELECT * FROM sbemojis WHERE name=? AND starboard_id=?"""
        emoji_name = str(emoji.id) if isinstance(emoji, discord.Emoji) else emoji
        emoji_id = emoji.id if isinstance(emoji, discord.Emoji) else None

        curr = self.db.cursor()
        async with self.db.lock:
            functions.check_or_create_existence(
                self.db, curr, self.bot, guild_id=ctx.guild.id, user_id=ctx.message.author.id, do_member=True
            )
            exists = functions.check_or_create_existence(self.db, curr, self.bot, starboard_id=starboard.id, guild_id=ctx.guild.id, create_new=False)
            if not exists['se']:
                await ctx.send("That is not a starboard!")
                return
            exists = len(curr.execute(check_sbemoji, [emoji_name, starboard.id]).fetchall()) > 0
            if exists:
                await ctx.send("That emoji is already on that starboard!")
                return
            curr.execute(self.db.q.create_sbemoji, [emoji_id, starboard.id, emoji_name, False])
        curr.close()
        await ctx.send(f"Added {emoji} to {starboard.mention}")

    @commands.command(
        name='removeEmoji', aliases=['removeemoji', 're'],
        description='Removes a starboard emoji',
        brief='Removes a starboard emoji'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def remove_starboard_emoji(self, ctx, starboard: discord.TextChannel, emoji: Union[discord.Emoji, str]):
        get_sbemoji = \
            """SELECT * FROM sbemojis WHERE name=? AND starboard_id=?"""
        del_sbemoji = \
            """DELETE FROM sbemojis WHERE id=?"""
        emoji_name = str(emoji.id) if isinstance(emoji, discord.Emoji) else emoji
        emoji_id = emoji.id if isinstance(emoji, discord.Emoji) else None

        curr = self.db.cursor()
        async with self.db.lock:
            functions.check_or_create_existence(
                self.db, curr, self.bot, guild_id=ctx.guild.id, user_id=ctx.message.author.id, do_member=True
            )
            exists = functions.check_or_create_existence(
                self.db, curr, self.bot, starboard_id=starboard.id, guild_id=ctx.guild.id, create_new=False
            )
            if not exists['se']:
                await ctx.send("That is not a starboard!")
                return
            rows = curr.execute(get_sbemoji, [emoji_name, starboard.id]).fetchall()
            if len(rows) == 0:
                await ctx.send("That is not a starboard emoji!")
                return
            sbemoji_id = rows[0]['id']
            curr.execute(del_sbemoji, [sbemoji_id])
        curr.close()
        await ctx.send(f"Removed {emoji} from {starboard.mention}")

    @commands.command(
        name='requiredStars', aliases=['rs', 'required', 'requiredstars'],
        description='Set\'s how many stars are needed before a message appears on the starboard',
        brief='Set\'s required stars'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_required_stars(self, ctx, starboard: discord.TextChannel, value: int):
        status = await change_starboard_settings(self.db, starboard.id, required=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Value")
        else:
            await ctx.send(f"Set requiredStars to {value} for {starboard.mention}")

    @commands.command(
        name='requiredToLose', aliases=['rtl', 'requiredtolose'],
        description='Set\'s how few stars a message needs before the messages is removed from the starboard',
        brief='Sets requiredToLose'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_required_to_lose(self, ctx, starboard: discord.TextChannel, value: int):
        status = await change_starboard_settings(self.db, starboard.id, rtl=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid setting")
        elif status is True:
            await ctx.send(f"Set requiredToLose to {value} for {starboard.mention}")

    @commands.command(
        name='selfStar', aliases=['ss', 'selfstar'],
        description='Set wether or not to allow a user to star their own message for starboard',
        brief='Set selfStar for starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def starboard_self_star(self, ctx, starboard: discord.TextChannel, value: bool):
        status = await change_starboard_settings(self.db, starboard.id, self_star=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set selfStar to {value} for {starboard.mention}")