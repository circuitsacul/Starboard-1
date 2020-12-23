from typing import Tuple, Optional, List

import discord
from discord.ext import commands, tasks

import functions
import errors
import bot_config


async def is_xpr(
    bot: commands.Bot,
    role_id: int
) -> bool:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            exists = await conn.fetchrow(
                """SELECT * FROM xproles
                WHERE id=$1""", role_id
            ) is not None
    return exists


async def get_role_by_xp(
    bot: commands.Bot,
    guild: discord.Guild,
    xp: int
) -> Tuple[Optional[dict], Optional[discord.Role], Optional[dict]]:
    get_lowest_xp = \
        """SELECT * FROM members
        WHERE guild_id=$1
        AND user_id=ANY($2::numeric[])
        ORDER BY xp ASC
        LIMIT 1"""

    conn = bot.db.conn

    roles_sql = await get_pos_roles(
        bot, guild.id
    )
    role_objects = [
        discord.utils.get(guild.roles, id=int(r['id']))
        for r in roles_sql
    ]

    role: discord.Role
    for x, role in enumerate(role_objects):
        if roles_sql[x]['max_users'] is None:
            return roles_sql[x], role, None
        if len(role.members) < roles_sql[x]['max_users']:
            return roles_sql[x], role, None

        mids = [m.id for m in role.members]
        async with bot.db.lock:
            async with conn.transaction():
                sql_lowest_member = await conn.fetchrow(
                    get_lowest_xp, guild.id, mids
                )

        _members = await functions.get_members(
            [int(sql_lowest_member['user_id'])], guild
        )
        if _members == []:
            replace_member = None
        else:
            replace_member = _members[0]

        if sql_lowest_member['xp'] < xp:
            return roles_sql[x], role, replace_member

    return None, None, None


async def update_user_roles(
    bot: commands.Bot,
    guild: discord.Guild,
    member: discord.Member
) -> None:
    get_member = \
        """SELECT * FROM members
        WHERE guild_id=$1
        AND user_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_member = await conn.fetchrow(
                get_member, guild.id, member.id
            )

    sql_role, role_obj, replace_member = await get_role_by_xp(
        bot, guild, sql_member['xp']
    )

    if not sql_role:
        return

    await member.add_roles(role_obj)
    if replace_member:
        await replace_member.remove_roles(role_obj)
        bot.dispatch('posrole_update', guild.id, replace_member.id)


async def get_pos_roles(
    bot: commands.Bot,
    guild_id: int
) -> List[dict]:
    fetch_roles = \
        """SELECT * FROM posroles
        WHERE guild_id=$1
        ORDER BY max_users ASC"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            pos_roles = await conn.fetch(
                fetch_roles, guild_id
            )

    return pos_roles


async def add_pos_role(
    bot: commands.Bot,
    role: discord.Role,
    max_users: int
) -> None:
    add_role = \
        """INSERT INTO posroles (id, guild_id, max_users)
        VALUES ($1, $2, $3)"""

    if not await functions.can_manage_role(
        bot, role
    ):
        raise discord.InvalidArgument(
            "I can't manage that role, probably "
            "because it is above my highest role."
        )

    limit = await functions.get_limit(
        bot, 'posroles', role.guild.id
    )

    if limit is False:
        raise errors.NoPremiumError(
            "Non-premium guilds do not have access "
            "to position-based Role Awards. See the "
            "last page of `sb!tutorial` for more info."
        )

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            current_num = await conn.fetchval(
                """SELECT COUNT (*) FROM posroles
                WHERE guild_id=$1""", role.guild.id
            )

    if current_num + 1 > limit:
        raise errors.NoPremiumError(
            "You have reached your limit for Position Roles"
        )

    if await is_xpr(bot, role.id):
        raise discord.InvalidArgument(
            "A role cannot be both an XP Role and "
            "a Position Role."
        )

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                add_role, role.id, role.guild.id,
                max_users
            )


async def remove_pos_role(
    bot: commands.Bot,
    role_id: discord.Role
) -> None:
    del_role = \
        """DELETE FROM posroles
        WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                del_role, role_id
            )


async def set_role_users(
    bot: commands.Bot,
    role_id: int,
    max_users: int
) -> None:
    update_role = \
        """UPDATE posroles
        SET max_users=$1
        WHERE id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                update_role, max_users, role_id
            )


class PositionRoles(commands.Cog):
    """Handles Position-based Roles"""

    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot
        self.queue = {}
        self.update_some_roles.start()

    @commands.Cog.listener()
    async def on_posrole_update(
        self,
        guild_id: int,
        member_id: int
    ) -> None:
        self.queue.setdefault(guild_id, [])
        self.queue[guild_id].append(member_id)

    @tasks.loop(seconds=1)
    async def update_some_roles(self):
        for guild_id in self.queue:
            mids = self.queue[guild_id]
            if len(mids) == 0:
                continue
            member_id = mids.pop(0)
            guild = self.bot.get_guild(guild_id)
            members = await functions.get_members([member_id], guild)
            if len(members) == 0:
                return
            member = members[0]
            await update_user_roles(self.bot, guild, member)

    @commands.command()
    async def test(self, ctx, uid: int):
        self.bot.dispatch('posrole_update', ctx.guild.id, uid)

    @commands.group(
        name='posroles', aliases=['pr', 'proles'],
        brief="Lists the servers Position-based Roles",
        invoke_without_command=True
    )
    @commands.guild_only()
    async def pos_roles(
        self,
        ctx: commands.Context
    ) -> None:
        pos_roles = await get_pos_roles(self.bot, ctx.guild.id)

        if len(pos_roles) == 0:
            await ctx.send("No Position Award Roles have been set.")
            return

        description = ""
        for r in pos_roles:
            description += f"<@&{r['id']}>: {r['max_users']}\n"

        embed = discord.Embed(
            title="Position Award Roles",
            description=description,
            color=bot_config.COLOR
        )

        await ctx.send(embed=embed)

    @pos_roles.command(
        name='add', aliases=['a', 'addRole'],
        brief="Adds a position-based award role"
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def add_pos_role(
        self,
        ctx: commands.Context,
        role: discord.Role,
        max_users: int
    ) -> None:
        await add_pos_role(
            self.bot, role, max_users
        )
        await ctx.send(
            f"**{role.name}** is now a Position-based Award Role."
        )

    @pos_roles.command(
        name='remove', aliases=['r', 'removeRole'],
        brief="Removes a Position Role"
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def remove_pos_role(
        self,
        ctx: commands.Context,
        role: discord.Role,
    ) -> None:
        await remove_pos_role(
            self.bot, role.id
        )
        await ctx.send(
            f"**{role.name}** is no longer a Position Role."
        )

    @pos_roles.command(
        name='setusers', aliases=['maxusers', 'users', 'max'],
        brief="Sets the max users of a Position Role"
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.guild_only()
    async def set_pos_role_users(
        self,
        ctx: commands.Context,
        role: discord.Role,
        max_users: int
    ) -> None:
        await set_role_users(
            self.bot, role.id, max_users
        )
        await ctx.send(
            f"Set the max users for **{role.name}** to "
            f"**{max_users}**."
        )


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(PositionRoles(bot))
