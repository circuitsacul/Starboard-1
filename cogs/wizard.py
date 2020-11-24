import discord
import functions
import asyncio
import bot_config
import emoji as emojilib
import settings
from paginators import disputils
from asyncio import sleep
from discord import utils
from settings import change_starboard_settings
from functions import pretty_emoji_string
from functions import get_limit
from typing import Union


def mybool(string: str):
    string = string.lower()
    if string[0] in ['y', 't']:
        return True
    elif string[0] in ['n', 'f']:
        return False
    raise ValueError("Please give either yes, no, true, or false.")


class SetupWizard:
    def __init__(self, ctx, bot, message=None):
        self.ctx = ctx
        self.bot = bot
        self.message = message
        self.running = True
        self.color = bot_config.COLOR
        self.mistake = bot_config.MISTAKE_COLOR

    async def run(self):
        self.running = True
        if self.message is None:
            embed = await self._get_embed("Please Wait...", self.color)
            self.message = await self.ctx.send(embed=embed)
            await sleep(0.5)

        while self.running:
            choice = await self._multi_choice(
                {
                    "Manage Starboards": 1,
                    "Manage AutoStar Channels": 2
                }
            )
            if choice is None:
                self.running = False
                await self.message.edit(content="Wizard Exitted", embed=None)
            elif choice == 1:
                await self.manage_starboards()
            elif choice == 2:
                await self.manage_aschannels()
            # elif choice == 3:
            #    pass

    async def manage_starboards(self) -> None:
        while True:
            new_or_modify = await self._multi_choice(
                {
                    "Create new starboard": 1,
                    "Modify existing starboard": 2,
                    "Delete a starboard": 3
                }
            )
            if new_or_modify is None:
                return
            elif new_or_modify == 1:
                await self.new_starboard()
            elif new_or_modify == 2:
                await self.modify_starboard()
            elif new_or_modify == 3:
                await self.delete_starboard()

    async def manage_aschannels(self) -> None:
        while True:
            choice = await self._multi_choice(
                {
                    "Create new autostar channel": 1,
                    "Modify existing autostar channel": 2,
                    "Delete an autostar channel": 3
                }
            )
            if choice is None:
                return
            elif choice == 1:
                await self.new_aschannel()
            elif choice == 2:
                await self.modify_aschannel()
            elif choice == 3:
                await self.delete_aschannel()

    async def new_aschannel(self) -> None:
        get_aschannels = """SELECT * FROM aschannels WHERE guild_id=$1"""

        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_aschannels = await conn.fetch(
                    get_aschannels, self.ctx.guild.id
                )
        current_num = len(sql_aschannels)
        limit = await get_limit(self.bot.db, 'aschannels', self.ctx.guild)
        if current_num >= limit:
            await self._error(
                "You have reached your limit for AutoStar Channels. "
                "In order to add more, the owner of this server must "
                "become a patron."
            )
            return

        new_or_used = await self._multi_choice(
            {"Create a new channel": 1, "Use an existing channel": 2}
        )
        if new_or_used is None:
            return
        channel = None
        channel_name = None
        if new_or_used == 1:
            channel_name = await self._input(
                "What should the AutoStar Channel be named?"
            )
            if channel_name is not None:
                channel = await self.ctx.guild.create_text_channel(
                    channel_name
                )
                await channel.set_permissions(
                    self.ctx.guild.me,
                    read_messages=True,
                    manage_messages=True,
                    add_reactions=True
                )
        elif new_or_used == 2:
            channel = await self._get_channel("What channel should I use?")

        if channel is None:
            return

        error = None
        status = True
        try:
            await settings.add_aschannel(
                self.bot, channel
            )
        except Exception as e:
            status = False
            error = str(e)

        if status is True:
            await self.message.edit(
                embed=await self._get_embed(
                    f"Created AutoStar Channel {channel.mention}",
                    self.color
                )
            )
            await sleep(1)
            await self._change_aschannel_settings(channel)
        else:
            await self._error(error)
            await self.new_aschannel()

    async def modify_aschannel(self) -> None:
        channel = await self._get_aschannel(
            "What autostar channel should I modify?"
        )
        if channel is False:
            await self._error("You don't have any autostar channels.")
            return
        if channel is None:
            return
        await self._change_aschannel_settings(channel)

    async def delete_aschannel(self) -> None:
        channel = await self._get_aschannel(
            "What AutoStar channel should I delete?"
        )
        if channel is False:
            await self._error("You don't have any autostar channels yet.")
            return
        if channel is None:
            return

        try:
            await settings.remove_aschannel(
                self.bot, channel.id, channel.guild.id
            )
        except Exception as e:
            await self._error(str(e))
            await self.delete_aschannel()

        await self.message.edit(embed=await self._get_embed(
            f"Deleted {channel.mention}",
            self.color
        ))
        await sleep(1)

    async def _change_aschannel_settings(
        self,
        channel: discord.TextChannel
    ) -> None:
        modifying = True
        while modifying:
            setting_indexes = {
                1: ('minChars', 'min_chars', int),
                2: ('requireImage', 'require_image', mybool),
                3: ('deleteInvalid', 'delete_invalid', mybool)
            }

            settings = await self._current_asc_settings(channel)
            choice = await self._multi_choice(
                settings, prompt=f"Modifying {channel.mention}"
            )
            if choice is None:
                modifying = False
            elif choice == 0:
                await self._manage_asc_emojis(channel)
            else:
                name, index, vtype = setting_indexes[choice]
                await self._change_asc_setting(
                    channel, name, index, vtype
                )

    async def new_starboard(self):
        get_starboards = """SELECT * FROM starboards WHERE guild_id=$1"""

        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_starboards = await conn.fetch(
                    get_starboards, self.ctx.guild.id
                )
        current_num = len(sql_starboards)
        limit = await get_limit(self.bot.db, 'starboards', self.ctx.guild)
        if current_num >= limit:
            await self._error(
                "You have reached your limit for starboards. Please upgrade "
                "by becoming a patron."
            )
            return

        new_or_used = await self._multi_choice(
            {"Create a new channel": 1, "Use an existing channel": 2}
        )
        if new_or_used is None:
            return
        channel_name = None
        channel = None
        if new_or_used == 1:
            channel_name = await self._input(
                "What should the starboard be named?"
            )
            if channel_name is not None:
                channel = await self.ctx.guild.create_text_channel(
                    channel_name
                )
                await channel.set_permissions(
                    self.ctx.guild.default_role,
                    send_messages=False
                )
                await channel.set_permissions(
                    self.ctx.guild.me,
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                    add_reactions=True,
                    read_message_history=True,
                )
        elif new_or_used == 2:
            channel = await self._get_channel("What channel should I use?")

        if channel is None:
            return

        error = None
        try:
            await settings.add_starboard(
                self.bot, channel
            )
            status = True
        except Exception as e:
            status = False
            error = str(e)

        if status is True:
            await self.message.edit(
                embed=await self._get_embed(
                    f"Created starboard {channel.mention}",
                    self.color
                )
            )
            await sleep(1)
            await self._change_starboard_settings(channel)
        else:
            await self._error(error)
            await self.new_starboard()

    async def modify_starboard(self):
        channel = await self._get_starboard("What starboard should I modify?")
        if channel is False:
            await self._error("You don't have any starboards yet.")
            return
        if channel is None:
            return
        await self._change_starboard_settings(channel)

    async def delete_starboard(self):
        channel = await self._get_starboard("What starboard should I delete?")
        if channel is False:
            await self._error("You don't have any starboards yet.")
            return
        if channel is None:
            return

        try:
            await settings.remove_starboard(
                self.bot, channel.id, channel.guild.id
            )
        except Exception as e:
            await self._error(str(e))
            return await self.delete_starboard()

        await self.message.edit(embed=await self._get_embed(
            f"Deleted {channel.mention}",
            self.color
        ))
        await sleep(1)

    async def _change_starboard_settings(self, channel):
        modifying = True
        while modifying:
            setting_indexes = {
                1: ('requiredStars', 'required', int),
                2: ('requiredToLose', 'rtl', int),
                3: ('linkDeletes', 'link_deletes', mybool),
                4: ('linkEdits', 'link_edits', mybool),
                5: ('selfStar', 'self_star', mybool),
                6: ('botsOnStarboard', 'bots_on_sb', mybool)
            }

            settings = await self._current_sb_settings(channel)
            choice = await self._multi_choice(
                settings, prompt=f"Modifying {channel.mention}"
            )
            if choice is None:
                modifying = False
            elif choice == 0:
                await self._manage_sb_emojis(channel)
            else:
                name, index, vtype = setting_indexes[choice]
                await self._change_sb_setting(channel, name, index, vtype)

    async def _manage_sb_emojis(self, channel):
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""
        modifying = True
        while modifying:
            async with self.bot.db.lock:
                conn = self.bot.db.conn
                async with conn.transaction():
                    _emojis = await conn.fetch(get_emojis, channel.id)
                    emojis = await pretty_emoji_string(_emojis, self.ctx.guild)
            options = {
                "Add Emoji": 1,
                "Remove Emoji": 2
            }
            choice = await self._multi_choice(options, emojis)
            if choice is None:
                modifying = False
            elif choice == 1:
                await self._add_sb_emoji(channel)
            elif choice == 2:
                await self._remove_sb_emoji(channel)

    async def _manage_asc_emojis(
        self,
        channel: discord.TextChannel
    ) -> None:
        get_emojis = """SELECT * FROM asemojis WHERE aschannel_id=$1"""
        modifying = True
        while modifying:
            async with self.bot.db.lock:
                conn = self.bot.db.conn
                async with conn.transaction():
                    _emojis = await conn.fetch(get_emojis, channel.id)
                    emojis = await pretty_emoji_string(_emojis, self.ctx.guild)
            options = {
                "Add Emoji": 1,
                "Remove Emoji": 2
            }
            choice = await self._multi_choice(options, emojis)
            if choice is None:
                modifying = False
            elif choice == 1:
                await self._add_asc_emoji(channel)
            elif choice == 2:
                await self._remove_asc_emoji(channel)

    async def _add_asc_emoji(
        self,
        channel: discord.TextChannel
    ) -> None:
        get_emojis = """SELECT * FROM asemojis WHERE aschannel_id=$1"""

        emoji_limit = await get_limit(
            self.bot.db, 'asemojis', self.ctx.guild
        )

        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_emojis = await conn.fetch(get_emojis, channel.id)

        current_num = len(sql_emojis)
        if current_num >= emoji_limit:
            await self._error(
                "You have reached yoru limit for emojis on this autostar "
                "channel. To add more, the owner of this server must "
                "become a patron."
            )
            return

        args = await self._get_emoji(
            "What emoji should I add?"
        )
        if args is None:
            return
        emoji_id, emoji_name = args
        if emoji_id is not None:
            emoji = utils.get(channel.guild.emojis, id=emoji_id)
        else:
            emoji = emoji_name
        
        try:
            await settings.add_asemoji(
                self.bot, channel, emoji
            )
        except Exception as e:
            await self._error(str(e))

    async def _remove_asc_emoji(
        self,
        channel: discord.TextChannel
    ) -> None:
        args = await self._get_emoji(
            "What emoji should I remove?"
        )
        if args is None:
            return
        emoji_id, emoji_name = args
        if emoji_id is not None:
            emoji = utils.get(channel.guild.emojis, id=emoji_id)
        else:
            emoji = emoji_name

        try:
            await settings.remove_asemoji(
                self.bot, channel, emoji
            )
        except Exception as e:
            await self._error(str(e))

    async def _add_sb_emoji(self, channel):
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""

        emoji_limit = await get_limit(
            self.bot.db, 'emojis', self.ctx.guild
        )

        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_emojis = await conn.fetch(get_emojis, channel.id)

        current_num = len(sql_emojis)
        if current_num >= emoji_limit:
            await self._error(
                "You have reached your limit for emojis on the starboard. "
                "Please upgrade by becoming a patron.",
            )
            return

        args = await self._get_emoji(
            "What emoji should I add?"
        )
        if args is None:
            return
        emoji_id, emoji_name = args
        if emoji_id is not None:
            emoji = utils.get(channel.guild.emojis, id=emoji_id)
        else:
            emoji = emoji_name

        try:
            await settings.add_starboard_emoji(
                self.bot, channel.id, channel.guild, emoji
            )
        except Exception as e:
            await self._error(str(e))

    async def _remove_sb_emoji(self, channel):
        args = await self._get_emoji(
            "What emoij do you want to delete?"
        )
        if args is None:
            return
        emoji_id, emoji_name = args
        if emoji_id is not None:
            emoji = utils.get(channel.guild.emojis, id=emoji_id)
        else:
            emoji = emoji_name

        try:
            await settings.remove_starboard_emoji(
                self.bot, channel.id, channel.guild, emoji
            )
        except Exception as e:
            await self._error(str(e))

    async def _get_emoji(self, prompt):
        inp = await self._input(prompt)
        if inp is None:
            return None
        emoji_name = None
        emoji_id = None
        try:
            emoji_id = int(
                inp.split(':')[2].replace('>', '')
            )
            _demoji = utils.get(self.ctx.guild.emojis, id=int(emoji_id))
            if _demoji is None:
                emoji_id = None
        except (ValueError, IndexError):
            if inp not in emojilib.UNICODE_EMOJI:
                emoji_name = None
            else:
                emoji_name = inp
        if emoji_name is None and emoji_id is None:
            await self._error(
                "I couldn't find that emoji",
            )
            return await self._get_emoji(prompt)
        return emoji_id, emoji_name

    async def _change_asc_setting(
        self,
        channel: discord.TextChannel,
        name: str,
        index: int,
        vtype: callable
    ) -> None:
        new_value = await self._input(f"Choose a new value for {name}")
        if new_value is None:
            return
        try:
            new_value = vtype(new_value)
        except ValueError:
            status = False
            error = "That is an invalid value!"
        else:
            status = await settings.change_aschannel_settings(
                self.bot.db, channel.id,
                min_chars=new_value if index == 'min_chars' else None,
                require_image=new_value if index == 'require_image' else None,
                delete_invalid=new_value if index == 'delete_invalid' else None
            )
            error = None

        if status is False:
            await self._error(error)
            return await self._change_asc_setting(
                channel, name, index, vtype
            )

    async def _change_sb_setting(self, channel, name, index, vtype):
        new_value = await self._input(f"Choose a new value for {name}")
        if new_value is None:
            return
        try:
            new_value = vtype(new_value)
        except ValueError:
            status = False
            error = "That is an invalid value!"
        else:
            status = await change_starboard_settings(
                self.bot.db, channel.id,
                self_star=new_value if index == 'self_star' else None,
                link_edits=new_value if index == 'link_edits' else None,
                link_deletes=new_value if index == 'link_deletes' else None,
                bots_on_sb=new_value if index == 'bots_on_sb' else None,
                required=new_value if index == 'required' else None,
                rtl=new_value if index == 'rtl' else None
            )
            error = None

        if status is False:
            if index == 'rtl' and error is None:
                error = "requiredToLose cannot be greater than or equal "\
                    "to requiredStars"
            elif index == 'required' and error is None:
                error = "requiredStars cannot be less than or equal to "\
                    "requiredToLose"
            await self._error(error)
            return await self._change_sb_setting(
                channel, name, index, vtype
            )

    async def _current_asc_settings(
        self,
        channel: discord.TextChannel
    ) -> dict:
        get_aschannel = \
            """SELECT * FROM aschannels WHERE id=$1"""
        get_emojis = \
            """SELECT * FROM asemojis WHERE aschannel_id=$1"""

        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_aschannel = await conn.fetchrow(
                    get_aschannel, channel.id
                )
                sql_emojis = await conn.fetch(
                    get_emojis, channel.id
                )
        emojis = await functions.pretty_emoji_string(
            sql_emojis, self.ctx.guild
        )
        settings = {
            f"emojis: {emojis}": 0,
            f"minChars: {sql_aschannel['min_chars']}": 1,
            f"requireImage: {sql_aschannel['require_image']}": 2,
            f"deleteInvalid: {sql_aschannel['delete_invalid']}": 3
        }
        return settings

    async def _current_sb_settings(self, channel):
        get_starboard = \
            """SELECT * FROM starboards WHERE id=$1"""
        get_emojis = \
            """SELECT * FROM sbemojis WHERE starboard_id=$1"""

        async with self.bot.db.lock:
            conn = await self.bot.db.connect()
            async with conn.transaction():
                sql_starboard = await conn.fetchrow(
                    get_starboard, channel.id
                )
                sql_emojis = await conn.fetch(
                    get_emojis, channel.id
                )
        emojis = await functions.pretty_emoji_string(
            sql_emojis, self.ctx.guild
        )
        settings = {
            f"emojis: {emojis}": 0,
            f"requiredStars: {sql_starboard['required']}": 1,
            f"requiredToLose: {sql_starboard['rtl']}": 2,
            f"linkDeletes: {sql_starboard['link_deletes']}": 3,
            f"linkEdits: {sql_starboard['link_edits']}": 4,
            f"selfStar: {sql_starboard['self_star']}": 5,
            f"botsOnStarboard: {sql_starboard['bots_on_sb']}": 6
        }
        return settings

    async def _check_starboard(self, channel_id):
        check = """SELECT * FROM starboards WHERE id=$1"""
        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_staboard = await conn.fetchrow(check, channel_id)
        if sql_staboard is None:
            return False
        else:
            return True

    async def _get_channel(self, prompt):
        channel_name = await self._input(prompt)
        if channel_name is None:
            return None
        channel = None
        try:
            by_id = int(
                channel_name.replace('>', '').replace('<', '').replace('#', '')
            )
            channel = utils.get(self.ctx.guild.channels, id=by_id)
        except ValueError:
            channel = utils.get(self.ctx.guild.channels, name=channel_name)
        if channel is None:
            await self._error(
                "I couldn't find that channel"
            )
            return await self._get_channel(prompt)
        return channel

    async def _get_aschannel(self, prompt: str) -> Union[dict, None]:
        get_aschannels = """SELECT * FROM aschannels WHERE guild_id=$1"""
        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_aschannels = await conn.fetch(
                    get_aschannels, self.ctx.guild.id
                )

        aschannels = []
        choices = {}
        for asc in sql_aschannels:
            _asc = utils.get(self.ctx.guild.channels, id=asc['id'])
            if _asc is None:
                continue
            aschannels.append(_asc)

        if len(aschannels) == 0:
            return False

        for x, asc in enumerate(aschannels):
            choices[asc.mention] = x

        choice = await self._multi_choice(choices, prompt)
        if choice is None:
            return None
        return aschannels[choice]

    async def _get_starboard(self, prompt):
        get_starboards = """SELECT * FROM starboards WHERE guild_id=$1"""
        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                sql_starboards = await conn.fetch(
                    get_starboards, self.ctx.guild.id
                )

        starboards = []
        choices = {}
        for sb in sql_starboards:
            _starboard = utils.get(self.ctx.guild.channels, id=sb['id'])
            if _starboard is None:
                continue
            starboards.append(_starboard)

        if len(starboards) == 0:
            return False

        for x, sb in enumerate(starboards):
            choices[sb.mention] = x

        choice = await self._multi_choice(choices, prompt)
        if choice is None:
            return None
        return starboards[choice]

    async def _multi_choice(self, options, prompt=""):
        mc = disputils.MultipleChoice(
            self.bot, [option for option in options],
            message=self.message, title="Setup Wizard",
            description=prompt, color=self.color
        )
        await mc.run([self.ctx.message.author])
        await self.message.clear_reactions()
        if mc.choice is None:
            return None
        return options[mc.choice]

    async def _input(self, prompt):
        embed = await self._get_embed(prompt, self.color)
        await self.message.edit(embed=embed)

        await self.message.add_reaction("❌")

        def msg_check(msg):
            if msg.author.id != self.ctx.message.author.id:
                return False
            elif msg.channel.id != self.ctx.message.channel.id:
                return False
            return True

        def react_check(reaction, user):
            if user.id != self.ctx.message.author.id:
                return False
            if reaction.message.id != self.message.id:
                return False
            return True

        tasks = [
            self.bot.wait_for('message', check=msg_check),
            self.bot.wait_for('reaction_add', check=react_check)
        ]

        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        done = [t for t in done]

        await self.message.clear_reactions()

        args = await done[0]
        if type(args) is discord.Message:
            inp = args
            await inp.delete()
            return inp.content
        else:
            return None

    async def _get_embed(self, content, color):
        embed = discord.Embed(
            title="Setup Wizard",
            description=content,
            color=color
        )
        return embed

    async def _error(self, content):
        embed = await self._get_embed(content, self.mistake)
        await self.message.edit(embed=embed)
        await self.message.add_reaction("🆗")

        def check(reaction, user):
            if reaction.message.id != self.message.id:
                return False
            if user.id != self.ctx.message.author.id:
                return False
            if reaction.emoji != "🆗":
                return False
            return True

        try:
            await self.bot.wait_for('reaction_add', check=check, timeout=30)
        except TimeoutError:
            pass

        try:
            await self.message.clear_reactions()
        except Exception:
            pass
