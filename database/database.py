import asyncpg as apg
import os
from asyncio import Lock
from discord import utils

db_pwd = os.getenv('DB_PWD')


class aobject(object):
    async def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs)
        return instance

    async def __init__(self):
        pass


class BotCache(aobject):
    async def __init__(self, event, limit=20):
        self._messages = {}
        self.limit = limit
        self.lock = Lock()
        await self.set_listeners(event)

    async def push(self, item, guild: int):
        async with self.lock:
            self._messages.setdefault(guild, [])
            self._messages[guild].append(item)
            if len(self._messages[guild]) > self.limit:
                self._messages[guild].pop(0)

    async def get(self, guild: int, **kwargs):
        async with self.lock:
            return utils.get(self._messages.get(guild, []), **kwargs)

    async def remove(self, msg_id: int, guild: int):
        status = False
        async with self.lock:
            remove_index = None
            for x, msg in enumerate(self._messages.get(guild, [])):
                if msg.id == msg_id:
                    remove_index = x
            if remove_index is not None:
                self._messages[guild].pop(remove_index)
                status = True
        return status

    async def set_listeners(self, event):
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
    async def __init__(self, conn):
        self.create_guild = \
            await conn.prepare(
                """INSERT INTO guilds (id) VALUES($1)"""
            )
        self.create_prefix = \
            await conn.prepare(
                """INSERT INTO prefixes (guild_id, prefix)
                VALUES($1, $2)"""
            )
        self.create_user = \
            await conn.prepare(
                """INSERT INTO users (id, is_bot)
                VALUES($1, $2)"""
            )
        self.create_patron = \
            await conn.prepare(
                """INSERT INTO patrons (user_id, product_id)
                VALUES($1, $2)"""
            )
        self.create_donation = \
            await conn.prepare(
                """INSERT INTO donations
                (txn_id, user_id, product_id, role_id, guild_id,
                email, price, currency, recurring, status)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)"""
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
                rtl=$6
                WHERE id=$7"""
            )


class Database:
    def __init__(self):
        self.lock = Lock()
        self.cooldowns = {
            'giving_stars': {}  # {user_id: cooldown_end_datetime}
        }
        self.conn = None

    async def open(self, bot):
        # self.q = await CommonSql()
        await self._create_tables()
        self.q = await CommonSql(await self.connect())
        self.cache = await BotCache(bot.event)

    async def connect(self):
        if self.conn is None:
            self.conn = await self.make_connection()
        return self.conn

    async def make_connection(self):
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
        return conn

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    async def _create_table(self, sql):
        conn = await self.connect()
        await conn.execute(sql)

    async def _create_tables(self):
        guilds_table = \
            """CREATE TABLE IF NOT EXISTS guilds (
                id numeric PRIMARY KEY,

                stars_given integer NOT NULL DEFAULT 0,
                stars_recv integer NOT NULL DEFAULT 0
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

                lvl_up_msgs bool DEFAULT True
            )"""

        patrons_table = \
            """CREATE TABLE IF NOT EXISTS patrons (
                id SERIAL PRIMARY KEY,
                user_id numeric NOT NULL,
                product_id text NOT NULL
            )"""

        donations_table = \
            """CREATE TABLE IF NOT EXISTS donations (
                id SERIAL PRIMARY KEY,
                txn_id integer NOT NULL,
                user_id integer NOT NULL,
                product_id text DEFAULT NULL,
                role_id numeric DEFAULT NULL,
                guild_id integer NOT NULL,

                email text NOT NULL,
                price integer NOT NULL,
                currency text NOT NULL,

                recurring bool NOT NULL,
                status text NOT NULL
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

                min_chars int NOT NULL DEFAULT 32,
                require_image bool NOT NULL DEFAULT False,
                delete_invalid bool NOT NULL DEFAULT False
            )"""

        asemojis_table = \
            """CREATE TABLE IF NOT EXISTS asemojis (
                id SERIAL PRIMARY KEY,
                aschannel_id numeric NOT NULL,

                name text NOT NULL

                FOREIGN KEY (aschannel_id) REFERENCED aschannels (id)
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

        await self.lock.acquire()
        await self._create_table(guilds_table)
        await self._create_table(prefixes_table)
        await self._create_table(users_table)
        await self._create_table(patrons_table)
        await self._create_table(donations_table)
        await self._create_table(members_table)
        await self._create_table(starboards_table)
        await self._create_table(sbemoijs_table)
        #await self._create_table(aschannels_table)
        #await self._create_table(asemojis_table)
        await self._create_table(messages_table)
        await self._create_table(reactions_table)
        self.lock.release()
