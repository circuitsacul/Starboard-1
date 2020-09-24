# TODO: Allow user to set botsReact, but also need to make it still ignore starboards reactions


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
        """SELECT * FROM starboards WHERE id=$1"""
    update_starboard = \
        """UPDATE starboards
        SET self_star=$1,
        link_edits=$2,
        link_deletes=$3,
        bots_react=$4,
        bots_on_sb=$5,
        required=$6,
        rtl=$7
        WHERE id=$8"""

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
        conn = await db.connect()
        c = await conn.cursor()
        await c.execute(get_starboard, [starboard_id])
        rows = await c.fetchall()
        if len(rows) == 0:
            await conn.close()
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

        if s['r'] <= s['rtl']:
            await conn.close()
            return False

        try:
            await c.execute(update_starboard, [
                s['ss'], s['le'], s['ld'], s['br'], s['bos'], s['r'], s['rtl'],
                starboard_id
            ])
        except Exception as e:
            print(e)
            await conn.close()
            return False
        await conn.commit()
        await conn.close()
    return True


async def pretty_emoji_string(emojis, guild):
    string = ""
    for emoji in emojis:
        is_custom = emoji['d_id'] is not None
        if is_custom:
            emoji_string = str(discord.utils.get(guild.emojis, id=int(emoji['d_id'])))
        else:
            emoji_string = emoji['name']
        string += emoji_string + " "
    return string


class Starboard(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='starboards', aliases=['boards', 'b'],
        description='List all the starboars for this server',
        brief='List starboards'
    )
    @commands.guild_only()
    async def list_starboards(self, ctx):
        get_starboards = """SELECT * FROM starboards WHERE guild_id=$1"""
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            _ = await functions.check_or_create_existence(self.db, c, self.bot, guild_id=ctx.guild.id, user=ctx.message.author, do_member=True)
            await c.execute(get_starboards, (ctx.guild.id,))
            rows = await c.fetchall()

            if len(rows) == 0:
                await ctx.send("You don't have any starboards")
            else:
                msg = f'Starboards: {len(rows)}\n'
                for row in rows:
                    sb_id = row['id']
                    await c.execute(get_emojis, [sb_id])
                    emojis = await c.fetchall()
                    emoji_string = await pretty_emoji_string(emojis, ctx.guild)
                    msg += f"--<#{row['id']}>: {emoji_string}\n"
                await ctx.send(msg)

            await conn.commit()
            await conn.close()

    @commands.command(
        name='settings', aliases=['s'],
        description='View all of the settings for a specific starboards',
        brief='View settings for startboard'
    )
    @commands.guild_only()
    async def get_starboard_settings(self, ctx, starboard: discord.TextChannel):
        get_starboard = """SELECT * FROM starboards WHERE id=$1"""
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            await functions.check_or_create_existence(self.db, c, self.bot, guild_id=ctx.guild.id, user=ctx.message.author, do_member=True)
            await c.execute(get_starboard, [starboard.id])
            sql_starboard = await c.fetchone()
            if sql_starboard is None:
                await ctx.send("That is not a starboard!")
            else:
                string = f"<#{starboard.id}>:**"
                string += f"\n--requiredStars: {sql_starboard['required']}"
                string += f"\n--requiredToLose: {sql_starboard['rtl']}"
                string += f"\n--selfStar: {bool(sql_starboard['self_star'])}"
                string += f"\n--linkEdits: {bool(sql_starboard['link_edits'])}"
                string += f"\n--linkDeletes: {bool(sql_starboard['link_deletes'])}"
                string += f"\n--botsReact: {bool(sql_starboard['bots_react'])}"
                string += f"\n--botsOnStarboard: {bool(sql_starboard['bots_on_sb'])}"
                string += f"\n--locked: {bool(sql_starboard['locked'])}"
                string += f"\n--archived: {bool(sql_starboard['is_archived'])}**"
                await ctx.send(string)
            await conn.close()

    @commands.command(
        name='add', aliases=['a'],
        description='Add a starboard',
        brief='Add a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def add_starboard(self, ctx, starboard: discord.TextChannel):
        perms = starboard.permissions_for(ctx.guild.me)
        if not perms.send_messages:
            await ctx.send("I can't send messages there.")
            return
        elif not perms.add_reactions:
            await ctx.send("I can't add reactions to messages there. If you want me to automatically add reactions, please enable this setting.")

        conn = await self.db.connect()
        c = await conn.cursor()
        get_starboards = \
            """SELECT * FROM starboards WHERE guild_id=$1"""

        limit = await functions.get_limit(self.db, 'starboards', ctx.guild)

        async with self.db.lock:
            await functions.check_or_create_existence(self.db, c, self.bot, guild_id=ctx.guild.id, user=ctx.message.author, do_member=True)
            await c.execute(get_starboards, [ctx.guild.id])
            rows = await c.fetchall()
            num_starboards = len(rows)

            if num_starboards >= limit:
                await ctx.send("You have reached your limit for starboards. Please upgrade by becoming a patron.")
            else:
                exists = await functions.check_or_create_existence(self.db, c, self.bot, guild_id=ctx.guild.id, starboard_id=starboard.id)
                if exists['se']:
                    await ctx.send("That is already a starboard!")
                else:
                    await ctx.send(f"Added starboard {starboard.mention}")

            await conn.commit()
            await conn.close()
        #if existed['se'] == True:
        #    await ctx.send("That is already a starboard!")
        #else:
        #    await ctx.send(f"Added starboard {starboard.mention}")

    @commands.command(
        name='remove', aliases=['r'],
        description='Remove a starboard',
        brief='Remove a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def remove_starboard(self, ctx, starboard: discord.TextChannel):
        confirmed = await functions.confirm(
            self.bot, ctx.channel,
            "Are you sure? All starboard messages will be lost forever.",
            ctx.message.author.id
        )

        if not confirmed:
            await ctx.send("Cancelling")
            return

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            await functions.check_or_create_existence(self.db, c, self.bot, guild_id=ctx.guild.id, user=ctx.message.author, do_member=True)
            existed = await functions.check_or_create_existence(self.db, c, self.bot, starboard_id=starboard.id, guild_id=ctx.guild.id, create_new=False)
            if existed['se'] == False:
                await ctx.send("That is not a starboard!")
                await conn.close()
                return
            remove_starboard = """DELETE FROM starboards WHERE id=$1"""
            await c.execute(remove_starboard, (starboard.id,))
            await conn.commit()
            await conn.close()
        await ctx.send("Removed starboard")

    @commands.command(
        name='addEmoji', aliases=['ae'],
        description='Add emoji to a starboard',
        brief='Add emoji to starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def add_starboard_emoji(self, ctx, starboard: discord.TextChannel, emoji: Union[discord.Emoji, str]):
        check_sbemoji = \
            """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
        get_all_sbemoji = \
            """SELECT * FROM sbemojis WHERE starboard_id=$3"""
        if not isinstance(emoji, discord.Emoji):
            if not functions.is_emoji(emoji):
                await ctx.send("I don't recognize that emoji. Please make sure it is correct, and if it's a custom emoji it has to be in this server.")
                return
        emoji_name = str(emoji.id) if isinstance(emoji, discord.Emoji) else emoji
        emoji_id = emoji.id if isinstance(emoji, discord.Emoji) else None

        limit = await functions.get_limit(self.db, 'emojis', ctx.guild)

        conn = await self.db.connect()
        c = await conn.cursor()
        added = False
        async with self.db.lock:
            await functions.check_or_create_existence(
                self.db, c, self.bot, guild_id=ctx.guild.id, user=ctx.message.author, do_member=True
            )
            exists = await functions.check_or_create_existence(self.db, c, self.bot, starboard_id=starboard.id, guild_id=ctx.guild.id, create_new=False)
            if not exists['se']:
                await ctx.send("That is not a starboard!")
            else:
                await c.execute(get_all_sbemoji, [starboard.id])
                rows = await c.fetchall()
                if len(rows) >= limit:
                    await ctx.send("You have reached your limit for emojis on this starboard. Please upgrade by becoming a patron.")
                else:
                    await c.execute(check_sbemoji, [emoji_name, starboard.id])
                    exists = len(await c.fetchall()) > 0
                    if exists:
                        await ctx.send("That emoji is already on that starboard!")
                    else:
                        await c.execute(self.db.q.create_sbemoji, [emoji_id, starboard.id, emoji_name, False])
                        added = True

            await conn.commit()
            await conn.close()
        if added:
            await ctx.send(f"Added {emoji} to {starboard.mention}")

    @commands.command(
        name='removeEmoji', aliases=['re'],
        description='Removes a starboard emoji',
        brief='Removes a starboard emoji'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def remove_starboard_emoji(self, ctx, starboard: discord.TextChannel, emoji: Union[discord.Emoji, str]):
        get_sbemoji = \
            """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
        del_sbemoji = \
            """DELETE FROM sbemojis WHERE id=$3"""
        emoji_name = str(emoji.id) if isinstance(emoji, discord.Emoji) else emoji
        emoji_id = emoji.id if isinstance(emoji, discord.Emoji) else None

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            await functions.check_or_create_existence(
                self.db, c, self.bot, guild_id=ctx.guild.id, user=ctx.message.author, do_member=True
            )
            exists = await functions.check_or_create_existence(
                self.db, c, self.bot, starboard_id=starboard.id, guild_id=ctx.guild.id, create_new=False
            )
            if not exists['se']:
                await ctx.send("That is not a starboard!")
                await conn.commit()
                await conn.close()
                return
            await c.execute(get_sbemoji, [emoji_name, starboard.id])
            rows = await c.fetchall()
            if len(rows) == 0:
                await ctx.send("That is not a starboard emoji!")
                await conn.commit()
                await conn.close()
                return
            sbemoji_id = rows[0]['id']
            await c.execute(del_sbemoji, [sbemoji_id])
            await conn.commit()
            await conn.close()
        await ctx.send(f"Removed {emoji} from {starboard.mention}")

    @commands.command(
        name='requiredStars', aliases=['rs', 'required'],
        description='Set\'s how many stars are needed before a message appears on the starboard',
        brief='Set\'s required stars'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_required_stars(self, ctx, starboard: discord.TextChannel, value: int):
        value = 1 if value < 1 else value
        status = await change_starboard_settings(self.db, starboard.id, required=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("RequiredStars cannot be less than or equal to RequiredToLose")
        else:
            await ctx.send(f"Set requiredStars to {value} for {starboard.mention}")

    @commands.command(
        name='requiredToLose', aliases=['rtl'],
        description='Set\'s how few stars a message needs before the messages is removed from the starboard',
        brief='Sets requiredToLose'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_required_to_lose(self, ctx, starboard: discord.TextChannel, value: int):
        value = -1 if value < -1 else value
        status = await change_starboard_settings(self.db, starboard.id, rtl=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("RequiredToLose cannot be greater than or equal to RequiredStars")
        elif status is True:
            await ctx.send(f"Set requiredToLose to {value} for {starboard.mention}")

    @commands.command(
        name='selfStar', aliases=['ss'],
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
            await ctx.send("Invalid Value")
        else:
            await ctx.send(f"Set selfStar to {value} for {starboard.mention}")

    @commands.command(
        name='linkEdits', aliases=['le'],
        description='Sets wether or not the bot should edit the starboard message if the user edits it',
        brief='Sets linkEdits for a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_link_edits(self, ctx, starboard: discord.TextChannel, value: bool):
        status = await change_starboard_settings(self.db, starboard.id, link_edits=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set linkEdits to {value} for {starboard.mention}")

    @commands.command(
        name='linkDeletes', aliases=['ld'],
        description='Sets wether or not the bot should delete the starboard message if the original is deleted',
        brief='Sets linkDeletes for a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_link_deletes(self, ctx, starboard: discord.TextChannel, value: bool):
        status = await change_starboard_settings(self.db, starboard.id, link_deletes=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set linkDeletes to {value} for {starboard.mention}")

    @commands.command(
        name='botsOnStarboard', aliases=['botsOnSb', 'bos'],
        description="Sets wether or not to allow bot messages to be put on the starboard",
        brief='Sets botsOnStarboards for a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_bots_on_starboard(self, ctx, starboard: discord.TextChannel, value: bool):
        status = await change_starboard_settings(self.db, starboard.id, bots_on_sb=value)
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set botsOnStarboard to {value} for {starboard.mention}")