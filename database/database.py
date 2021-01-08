import asyncpg as apg
import os
import time
from discord.ext import commands
from dotenv import load_dotenv
from asyncio import Lock
from discord import utils
from typing import Any

load_dotenv()
db_pwd = os.getenv('DB_PWD')


class aobject(object):
    async def __new__(
        cls: Any,
        *args,
        **kwargs
    ) -> Any:
        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs)
        return instance

    async def __init__(self) -> None:
        pass


class CustomConn:
    def __init__(
        self,
        realcon: apg.Connection
    ) -> None:
        self.realcon = realcon
        self.sql_dict = {}

    async def dump(self) -> None:  # requires external lock
        add_row = \
            """INSERT INTO sqlruntimes (sql, count, time)
            values ($1, $2, $3)"""
        update_row = \
            """UPDATE sqlruntimes
            SET count=$2,
            time=$3
            WHERE sql=$1"""
        check_row = \
            """SELECT * FROM sqlruntimes
            WHERE sql=$1"""

        conn = self.realcon

        async with self.realcon.transaction():
            for sql, d in self.sql_dict.items():
                row = await conn.fetchrow(check_row, sql)
                if row is None:
                    await conn.execute(
                        add_row, sql, d['c'], d['e']
                    )
                else:
                    await conn.execute(
                        update_row, sql,
                        d['c']+row['count'],
                        d['e']+float(row['time'])
                    )

        self.sql_dict = {}

    def transaction(
        self, *args, **kwargs
    ):
        return self.realcon.transaction(*args, **kwargs)

    def log(
        self,
        sql: str,
        time: float
    ) -> None:
        sql = sql.lower()
        self.sql_dict.setdefault(sql, {'c': 0, 'e': 0})
        self.sql_dict[sql]['c'] += 1
        self.sql_dict[sql]['e'] += time

    async def prepare(
        self,
        *args, **kwargs
    ) -> None:
        return await self.realcon.prepare(*args, **kwargs)

    async def execute(
        self,
        sql: str,
        *args, **kwargs
    ):
        s = time.time()
        result = await self.realcon.execute(sql, *args, **kwargs)
        self.log(sql, time.time() - s)
        return result

    async def fetch(
        self,
        sql: str,
        *args, **kwargs
    ):
        s = time.time()
        result = await self.realcon.fetch(sql, *args, **kwargs)
        self.log(sql, time.time() - s)
        return result

    async def fetchrow(
        self,
        sql: str,
        *args, **kwargs
    ):
        s = time.time()
        result = await self.realcon.fetchrow(sql, *args, **kwargs)
        self.log(sql, time.time() - s)
        return result

    async def fetchval(self, sql, *args, **kwargs):
        s = time.time()
        result = await self.realcon.fetchval(sql, *args, **kwargs)
        self.log(sql, time.time() - s)
        return result


class BotCache(aobject):
    async def __init__(
        self,
        event,
        limit: int = 20
    ) -> None:
        self._messages = {}
        self.limit = limit
        await self.set_listeners(event)

    async def push(
        self,
        item: Any,
        guild: int
    ) -> None:
        self._messages.setdefault(guild, [])
        self._messages[guild].append(item)
        if len(self._messages[guild]) > self.limit:
            self._messages[guild].pop(0)

    async def get(
        self,
        guild: int,
        **kwargs
    ) -> Any:
        return utils.get(self._messages.get(guild, []), **kwargs)

    async def remove(
        self,
        msg_id: int,
        guild: int
    ) -> bool:
        status = False
        remove_index = None
        for x, msg in enumerate(self._messages.get(guild, [])):
            if msg.id == msg_id:
                remove_index = x
        if remove_index is not None:
            self._messages[guild].pop(remove_index)
            status = True
        return status

    async def set_listeners(
        self,
        event
    ) -> None:
        @event
        async def on_raw_message_delete(payload):
            if payload.guild_id is None:
                return
            await self.remove(payload.message_id, payload.guild_id)

        @event
        async def on_message_edit(before, after):
            if before.guild is None:
                return
            status = await self.remove(before.id, before.guild.id)
            if status is True:
                await self.push(after, after.guild.id)

        @event
        async def on_raw_bulk_message_delete(payload):
            if payload.guild_id is None:
                return
            ids = payload.message_ids
            for id in ids:
                await self.remove(id, payload.guild_id)


class CommonSql(aobject):
    async def __init__(
        self,
        conn: apg.Connection
    ) -> None:
        self.create_guild = \
            await conn.prepare(
                """INSERT INTO guilds (id) VALUES($1)"""
            )
        self.create_user = \
            await conn.prepare(
                """INSERT INTO users (id, is_bot)
                VALUES($1, $2)"""
            )
        self.create_vote = \
            await conn.prepare(
                """INSERT INTO votes (user_id, expires)
                VALUES($1, $2)"""
            )
        self.create_member = \
            await conn.prepare(
                """INSERT INTO members (user_id, guild_id)
                VALUES($1,$2)"""
            )
        self.create_starboard = \
            await conn.prepare(
                """INSERT INTO starboards (id, guild_id)
                VALUES($1,$2)"""
            )
        self.create_sbemoji = \
            await conn.prepare(
                """INSERT INTO sbemojis (d_id, starboard_id,
                name, is_downvote)
                VALUES($1,$2,$3,$4)"""
            )
        self.create_aschannel = \
            await conn.prepare(
                """INSERT INTO aschannels (id, guild_id)
                VALUES($1, $2)"""
            )
        self.create_asemoji = \
            await conn.prepare(
                """INSERT INTO asemojis (aschannel_id, name)
                VALUES($1, $2)"""
            )
        self.create_channelbl = \
            await conn.prepare(
                """INSERT INTO channelbl (starboard_id, channel_id, guild_id, is_whitelist)
                VALUES($1, $2, $3, $4)"""
            )
        self.create_rolebl = \
            await conn.prepare(
                """INSERT INTO rolebl (starboard_id, role_id, guild_id, is_whitelist)
                VALUES($1, $2, $3, $4)"""
            )
        self.create_message = \
            await conn.prepare(
                """INSERT INTO messages (id, guild_id,
                user_id, orig_message_id, channel_id,
                is_orig, is_nsfw)
                VALUES($1,$2,$3,$4,$5,$6,$7)"""
            )
        self.create_reaction = \
            await conn.prepare(
                """INSERT INTO reactions (guild_id,
                user_id, message_id, name)
                VALUES ($1,$2,$3,$4)"""
            )

        self.update_starboard = \
            await conn.prepare(
                """UPDATE starboards
                SET self_star=$1,
                link_edits=$2,
                link_deletes=$3,
                bots_on_sb=$4,
                required=$5,
                rtl=$6,
                require_image=$7
                WHERE id=$8"""
            )


class Database:
    def __init__(self) -> None:
        self.lock = Lock()
        self.cooldowns = {
            'giving_stars': {}  # {user_id: cooldown_end_datetime}
        }
        self.conn = None
        self.cache = None
        self.as_cache = None

    async def open(
        self,
        bot: commands.Bot
    ) -> None:
        # self.q = await CommonSql()
        await self._create_tables()
        await self._apply_migrations()
        self.q = await CommonSql(await self.connect())
        self.cache = await BotCache(bot.event)

    async def connect(self) -> CustomConn:
        if self.conn is None:
            self.conn = await self.make_connection()
        return self.conn

    async def make_connection(self) -> CustomConn:
        conn = None
        try:
            conn = await apg.connect(
                host='localhost', database='starboard',
                user='starboard', password=db_pwd
            )
            # await conn.execute(
            #    "PRAGMA foreign_keys=True"
            # )
            # conn.row_factory = self._dict_factory
        except Exception as e:
            print(f"Couldn't connect to database: {e}")
            if conn:
                await conn.close()
        customconn = CustomConn(conn)
        return customconn

    def _dict_factory(self, cursor, row) -> dict:
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    async def _create_table(self, sql: str) -> None:
        conn = await self.connect()
        await conn.realcon.execute(sql)

    async def _create_index(self, sql: str) -> None:
        conn = await self.connect()
        await conn.realcon.execute(sql)

    async def _apply_migration(self, sql: str) -> None:
        conn = await self.connect()
        await conn.realcon.execute(sql)

    async def _apply_migrations(self) -> None:
        messages__addcolumn__points = \
            """ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS points int DEFAULT NULL
            """
        guilds__addcolumn__prefixes = \
            """ALTER TABLE guilds
            ADD COLUMN IF NOT EXISTS prefixes VARCHAR(8) ARRAY
            DEFAULT '{"sb!"}'"""
        deltable__prefixes = \
            """DROP TABLE IF EXISTS prefixes"""
        deltable__patrons = \
            """DROP TABLE IF EXISTS patrons"""
        deltable__donations = \
            """DROP TABLE IF EXISTS donations"""
        users__addcolumn__credits = \
            """ALTER TABLE users
            ADD COLUMN IF NOT EXISTS credits int DEFAULT 0"""
        users__addcolumn__payment = \
            """ALTER TABLE users
            ADD COLUMN IF NOT EXISTS payment smallint DEFAULT 0"""
        guilds__addcolumn__premium_end = \
            """ALTER TABLE guilds
            ADD COLUMN IF NOT EXISTS premium_end
            timestamp DEFAULT NULL"""
        aschannels__addcolumn__locked = \
            """ALTER TABLE aschannels
            ADD COLUMN IF NOT EXISTS locked
            bool NOT NULL DEFAULT False"""
        members__addcolumn__autoredeem = \
            """ALTER TABLE members
            ADD COLUMN IF NOT EXISTS autoredeem
            bool NOT NULL DEFAULT False"""
        guilds__addcolumn__is_qa_on = \
            """ALTER TABLE guilds
            ADD COLUMN IF NOT EXISTS is_qa_on
            bool NOT NULL DEFAULT False"""
        starboards__addcolumn__require_image = \
            """ALTER TABLE starboards
            ADD COLUMN IF NOT EXISTS require_image
            BOOL NOT NULL DEFAULT False"""

        await self.lock.acquire()
        await self._apply_migration(messages__addcolumn__points)
        await self._apply_migration(guilds__addcolumn__prefixes)
        await self._apply_migration(deltable__prefixes)
        await self._apply_migration(deltable__patrons)
        await self._apply_migration(deltable__donations)
        await self._apply_migration(users__addcolumn__credits)
        await self._apply_migration(users__addcolumn__payment)
        await self._apply_migration(guilds__addcolumn__premium_end)
        await self._apply_migration(aschannels__addcolumn__locked)
        await self._apply_migration(members__addcolumn__autoredeem)
        await self._apply_migration(guilds__addcolumn__is_qa_on)
        await self._apply_migration(starboards__addcolumn__require_image)
        self.lock.release()

    async def _create_tables(self) -> None:
        guilds_table = \
            """CREATE TABLE IF NOT EXISTS guilds (
                id numeric PRIMARY KEY,
                prefixes VARCHAR(8) ARRAY DEFAULT "{'sb!'}",
                is_qa_on bool NOT NULL DEFAULT False,

                premium_end timestamp DEFAULT NULL,

                stars_given integer NOT NULL DEFAULT 0,
                stars_recv integer NOT NULL DEFAULT 0
            )"""

        xproles_table = \
            """CREATE TABLE IF NOT EXISTS xproles (
                id numeric PRIMARY KEY,
                guild_id numeric NOT NULL,
                req_xp smallint NOT NULL,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        posroles_table = \
            """CREATE TABLE IF NOT EXISTS posroles (
                id numeric PRIMARY KEY,
                guild_id numeric NOT NULL,
                max_users smallint NOT NULL,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        prefixes_table = \
            """CREATE TABLE IF NOT EXISTS prefixes (
                id SERIAL PRIMARY KEY,
                guild_id numeric NOT NULL,
                prefix VARCHAR(8),

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        users_table = \
            """CREATE TABLE IF NOT EXISTS users (
                id numeric PRIMARY KEY,
                is_bot bool NOT NULL,

                payment smallint DEFAULT 0,
                credits int DEFAULT 0,

                lvl_up_msgs bool DEFAULT True
            )"""

        votes_table = \
            """CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                user_id numeric NOT NULL,
                expires numeric NOT NULL,
                expired bool DEFAULT false,

                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE
            )"""

        payrolls_table = \
            """CREATE TABLE IF NOT EXISTS payrolls (
                paydate timestamp NOT NULL
            )"""

        members_table = \
            """CREATE TABLE IF NOT EXISTS members (
                id SERIAL PRIMARY KEY,
                user_id numeric NOT NULL,
                guild_id numeric NOT NULL,

                given int NOT NULL DEFAULT 0,
                received int NOT NULL DEFAULT 0,

                xp int NOT NULL DEFAULT 0,
                lvl int NOT NULL DEFAULT 0,

                autoredeem bool NOT NULL DEFAULT False,

                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        starboards_table = \
            """CREATE TABLE IF NOT EXISTS starboards (
                id numeric PRIMARY KEY,
                guild_id numeric NOT NULL,

                required int NOT NULL DEFAULT 3,
                rtl int NOT NULL DEFAULT 0,

                self_star bool NOT NULL DEFAULT false,
                link_edits bool NOT NULL DEFAULT true,
                link_deletes bool NOT NULL DEFAULT false,
                bots_on_sb bool NOT NULL DEFAULT true,
                require_image bool NOT NULL DEFAULT false,

                locked bool NOT NULL DEFAULT false,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        sbemoijs_table = \
            """CREATE TABLE IF NOT EXISTS sbemojis (
                id SERIAL PRIMARY KEY,
                d_id numeric,
                starboard_id numeric NOT NULL,

                name text NOT NULL,
                is_downvote bool NOT NULL DEFAULT false,

                FOREIGN KEY (starboard_id) REFERENCES starboards (id)
                    ON DELETE CASCADE
            )"""

        aschannels_table = \
            """CREATE TABLE IF NOT EXISTS aschannels (
                id numeric PRIMARY KEY,
                guild_id numeric NOT NULL,

                min_chars int NOT NULL DEFAULT 0,
                require_image bool NOT NULL DEFAULT False,
                delete_invalid bool NOT NULL DEFAULT False,

                locked bool NOT NULL DEFAULT False
            )"""

        asemojis_table = \
            """CREATE TABLE IF NOT EXISTS asemojis (
                id SERIAL PRIMARY KEY,
                aschannel_id numeric NOT NULL,

                name text NOT NULL,

                FOREIGN KEY (aschannel_id) REFERENCES aschannels (id)
                    ON DELETE CASCADE
            )"""

        channelbl_table = \
            """CREATE TABLE IF NOT EXISTS channelbl (
                starboard_id numeric NOT NULL,
                channel_id numeric NOT NULL,
                guild_id numeric NOT NULL,
                is_whitelist bool NOT NULL DEFAULT False,

                FOREIGN KEY (starboard_id) REFERENCES starboards (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        rolebl_table = \
            """CREATE TABLE IF NOT EXISTS rolebl (
                starboard_id numeric NOT NULL,
                role_id numeric NOT NULL,
                guild_id numeric NOT NULL,
                is_whitelist bool NOT NULL DEFAULT False,

                FOREIGN KEY (starboard_id) REFERENCES starboards (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        messages_table = \
            """CREATE TABLE IF NOT EXISTS messages (
                id numeric PRIMARY KEY,
                guild_id numeric NOT NULL,
                user_id numeric NOT NULL,
                orig_message_id numeric DEFAULT NULL,
                channel_id numeric NOT NULL,

                is_orig bool NOT NULL,
                is_nsfw bool NOT NULL,
                is_trashed bool NOT NULL DEFAULT false,
                is_frozen bool NOT NULL DEFAULT false,
                is_forced bool NOT NULL DEFAULT false,

                points int DEFAULT NULL,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (orig_message_id) REFERENCES messages (id)
                    ON DELETE CASCADE
            )"""

        reactions_table = \
            """CREATE TABLE IF NOT EXISTS reactions (
                id SERIAL PRIMARY KEY,
                guild_id numeric NOT NULL,
                user_id numeric NOT NULL,
                message_id numeric NOT NULL,

                name text NOT NULL,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )"""

        sqlruntimes_table = \
            """CREATE TABLE IF NOT EXISTS sqlruntimes (
                sql TEXT PRIMARY KEY,
                count integer NOT NULL DEFAULT 0,
                time numeric NOT NULL DEFAULT 0
            )"""

        delete_reaction_index = \
            """CREATE INDEX IF NOT EXISTS delete_reaction
            ON reactions(message_id, user_id, name)"""

        msg_orig_msg_id_index = \
            """CREATE INDEX IF NOT EXISTS msg_id
            ON messages(orig_message_id)"""

        member_uid_index = \
            """CREATE INDEX IF NOT EXISTS member_uid
            ON members(user_id)"""

        sbemojis_starboard_index = \
            """CREATE INDEX IF NOT EXISTS sbemojis_starboard_id
            ON sbemojis(starboard_id)"""

        messages_guild_id_index = \
            """CREATE INDEX IF NOT EXISTS messages_guild_id
            ON messages(guild_id)"""

        await self.lock.acquire()

        await self._create_table(guilds_table)
        await self._create_table(xproles_table)
        await self._create_table(posroles_table)
        await self._create_table(prefixes_table)
        await self._create_table(users_table)
        await self._create_table(votes_table)
        await self._create_table(payrolls_table)
        await self._create_table(members_table)
        await self._create_table(starboards_table)
        await self._create_table(sbemoijs_table)
        await self._create_table(aschannels_table)
        await self._create_table(asemojis_table)
        await self._create_table(channelbl_table)
        await self._create_table(rolebl_table)
        await self._create_table(messages_table)
        await self._create_table(reactions_table)
        await self._create_table(sqlruntimes_table)

        await self._create_index(delete_reaction_index)
        await self._create_index(msg_orig_msg_id_index)
        await self._create_index(member_uid_index)
        await self._create_index(sbemojis_starboard_index)
        await self._create_table(messages_guild_id_index)

        self.lock.release()
