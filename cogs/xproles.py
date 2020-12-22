from typing import List
from copy import deepcopy

import discord
from discord.ext import commands, tasks

import bot_config
import functions
import errors


async def is_pr(
    bot: commands.Bot,
    role_id: int
) -> bool:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            exists = await conn.fetchrow(
                """SELECT * FROM posroles
                WHERE id=$1""", role_id
            ) is not None
    return exists


async def update_user_xproles(
    bot: commands.Bot,
    guild: discord.Guild,
    user: discord.Member
) -> None:
    get_member = \
        """SELECT * FROM members
        WHERE user_id=$1
        AND guild_id=$2"""

    limit = await functions.get_limit(
        bot, 'xproles', guild.id
    )
    if limit is False:
        return

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_member = await conn.fetchrow(
                get_member, user.id, guild.id
            )

    xp = int(sql_member['xp'])
    gets_xp_roles: List[int] = [
        int(r['id']) for r in
        await get_roles_by_xp(
            bot, guild.id, xp, True
        )
    ]
    all_xp_roles: List[int] = [
        int(r['id']) for r in
        await get_xp_roles(
            bot, guild
        )
    ]
    has_roles_ids: List[int] = [r.id for r in user.roles]

    remove_roles = []
    give_roles = []

    for role in guild.roles:
        if role.position >= guild.me.top_role.position:
            # the bot can't edit this role
            continue
        if role.id in all_xp_roles\
                and role.id in has_roles_ids\
                and role.id not in gets_xp_roles:
            remove_roles.append(role)
        elif role.id in all_xp_roles and role.id in gets_xp_roles:
            give_roles.append(role)

    await user.remove_roles(*remove_roles)
    await user.add_roles(*give_roles)


async def get_xp_roles(
    bot: commands.Bot,
    guild: discord.Guild
) -> List[dict]:
    fetch_roles = \
        """SELECT * FROM xproles WHERE guild_id=$1
        ORDER by req_xp DESC"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_xp_roles = await conn.fetch(
                fetch_roles, guild.id
            )

    return sql_xp_roles


async def get_roles_by_xp(
    bot: commands.Bot,
    guild_id: int,
    xp: int,
    stack: bool
) -> List[dict]:
    fetch_roles = \
        """SELECT * FROM xproles
        WHERE guild_id=$1
        AND req_xp<$2
        ORDER BY req_xp DESC
        LIMIT $3"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_roles = await conn.fetch(
                fetch_roles, guild_id,
                xp, None if stack else 1
            )

    return sql_roles


async def add_xp_role(
    bot: commands.Bot,
    role: discord.Role,
    req_xp: int
) -> None:
    if not await functions.can_manage_role(
        bot, role
    ):
        raise discord.InvalidArgument(
            "I can't manage that role, "
            "probably because that role "
            "is higher than my top role."
        )
    limit = await functions.get_limit(
        bot, 'xproles', role.guild.id
    )
    if limit is False:
        raise errors.NoPremiumError(
            "Non-premium guilds do not have "
            "access to XP Roles. See the last "
            "page of `sb!tutorial` for more info."
        )

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            current_num = await conn.fetchval(
                """SELECT COUNT(*) FROM xproles
                WHERE guild_id=$1""", role.guild.id
            )

    if current_num + 1 > limit:
        raise errors.NoPremiumError(
            "You have reached your limit for XP Roles."
        )

    if await is_pr(bot, role.id):
        raise discord.InvalidArgument(
            "A role cannot be both a Position Role "
            "and an XP Role."
        )

    if not 0 <= req_xp < 100000:
        raise discord.errors.InvalidArgument(
            "Required XP must be greater than or "
            "equal to 0 and less than 100,000"
        )
    create_xp_role = \
        """INSERT INTO xproles (id, guild_id, req_xp)
        VALUES ($1, $2, $3)"""

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                create_xp_role,
                role.id, role.guild.id,
                req_xp
            )


async def del_xp_role(
    bot: commands.Bot,
    role_id: int
) -> None:
    sql_del_role = \
        """DELETE FROM xproles
        WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                sql_del_role, role_id
            )


async def set_role_xp(
    bot: commands.Bot,
    role_id: int,
    req_xp: int
) -> None:
    alter_role = \
        """UPDATE xproles
        SET req_xp=$1
        WHERE id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                alter_role, req_xp, role_id
            )


class XPRoles(commands.Cog):
    """Handles XP roles"""

    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot
        self.queue = {}
        self.update_some_roles.start()

    @commands.Cog.listener()
    async def on_xpr_needs_update(
        self,
        guild_id: int,
        user_id: int
    ) -> None:
        self.queue.setdefault(guild_id, [])
        self.queue[guild_id].append(user_id)

    @tasks.loop(seconds=1)
    async def update_some_roles(self) -> None:
        queue = deepcopy(self.queue)
        for gid in queue:
            if len(queue[gid]) == 0:
                return
            guild = self.bot.get_guild(gid)
            uid = self.queue[gid].pop(0)
            members = await functions.get_members(
                [uid], guild
            )
            if len(members) == 0:
                return
            member = members[0]
            await update_user_xproles(
                self.bot, guild, member
            )

    @commands.group(
        name='xproles', aliases=['xpr'],
        brief="View server XP roles",
        invoke_without_command=True
    )
    @commands.guild_only()
    async def xp_roles(
        self,
        ctx: commands.Context
    ) -> None:
        xp_roles = await get_xp_roles(
            self.bot, ctx.guild
        )
        if len(xp_roles) == 0:
            await ctx.send("You have no XP Roles set.")
            return

        description = ""
        for role in xp_roles:
            description += f"<@&{role['id']}>: {role['req_xp']}\n"

        embed = discord.Embed(
            title="XP Roles",
            description=description,
            color=bot_config.COLOR
        )

        await ctx.send(embed=embed)

    @xp_roles.command(
        name='add', aliases=['a', 'addRole'],
        brief="Adds an XP role"
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def add_xp_role(
        self,
        ctx: commands.Context,
        role: discord.Role,
        required_xp: int
    ) -> None:
        await add_xp_role(
            self.bot, role,
            required_xp
        )
        await ctx.send(f"**{role.name}** is now an XP Role")

    @xp_roles.command(
        name='remove', aliases=['r', 'removeRole'],
        brief="Removes an XP Role"
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def remove_xp_role(
        self,
        ctx: commands.Context,
        role: discord.Role,
    ) -> None:
        await del_xp_role(
            self.bot, role if type(role) is int else role.id
        )
        await ctx.send(f"Removed XP Role **{role}**")

    @xp_roles.command(
        name='requiredXP', aliases=['required', 'xp'],
        brief="Sets the required XP of an XP Role"
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def set_xp_role_xp(
        self,
        ctx: commands.Context,
        role: discord.Role,
        required_xp: int
    ) -> None:
        await set_role_xp(
            self.bot, role.id, required_xp
        )
        await ctx.send(
            f"Set the required XP for **{role}** to "
            f"**{required_xp}**."
        )


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(XPRoles(bot))
