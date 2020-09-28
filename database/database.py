import asyncpg as apg
from aiosqlite import Error
from asyncio import Lock


class aobject(object):
    async def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        await instance.__init__(*args, **kwargs)
        return instance

    async def __init__(self):
        pass


class CommonSql(aobject):
    async def __init__(self, conn):
        self.create_guild = \
            await conn.prepare(
                """INSERT INTO guilds (id) VALUES($1)"""
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
        self.create_message = \
            await conn.prepare(
                """INSERT INTO messages (id, guild_id,
                user_id, orig_message_id, channel_id,
                is_orig, is_nsfw)
                VALUES($1,$2,$3,$4,$5,$6,$7)"""
            )
        self.create_reaction = \
            await conn.prepare(
                """INSERT INTO reactions (d_id, guild_id,
                user_id, message_id, name)
                VALUES ($1,$2,$3,$4,$5)"""
            )

        self.update_starboard = \
            await conn.prepare(
                """UPDATE starboards
                SET self_star=$1,
                link_edits=$2,
                link_deletes=$3,
                bots_react=$4,
                bots_on_sb=$5,
                required=$6,
                rtl=$7
                WHERE id=$8"""
            )


class Database:
    def __init__(self, db_path):
        self.lock = Lock()
        #self.q = CommonSql()
        self._db_path = db_path
        self.cooldowns = {
            'giving_stars': {} # {user_id: cooldown_end_datetime}
        }

    async def open(self):
        #self.q = await CommonSql()
        await self._create_tables()
        self.q = await CommonSql(await self.connect())

    async def connect(self):
        conn = None
        try:
            conn = await apg.connect(host='localhost', database='starboarddb', user='ld', password='password')
            #await conn.execute(
            #    "PRAGMA foreign_keys=True"
            #)
            #conn.row_factory = self._dict_factory
        except Error as e:
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
        print("Creating table")
        #cursor = self.cursor()
        conn = await self.connect()
        await conn.execute(sql)
        #c = await conn.cursor()
        #await c.execute(sql)
        #await conn.commit()
        await conn.close()

    async def _create_tables(self):
        guilds_table = \
            """CREATE TABLE IF NOT EXISTS guilds (
                id text PRIMARY KEY,

                stars_given integer NOT NULL DEFAULT 0,
                stars_recv integer NOT NULL DEFAULT 0
            )"""

        users_table = \
            """CREATE TABLE IF NOT EXISTS users (
                id text PRIMARY KEY,
                is_bot bool NOT NULL,

                lvl_up_msgs bool DEFAULT True
            )"""

        patrons_table = \
            """CREATE TABLE IF NOT EXISTS patrons (
                id SERIAL PRIMARY KEY,
                user_id text NOT NULL,
                product_id text NOT NULL
            )"""

        donations_table = \
            """CREATE TABLE IF NOT EXISTS donations (
                id SERIAL PRIMARY KEY,
                txn_id integer NOT NULL,
                user_id integer NOT NULL,
                product_id text DEFAULT NULL,
                role_id text DEFAULT NULL,
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
                user_id text NOT NULL,
                guild_id text NOT NULL,

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
                id text PRIMARY KEY,
                guild_id text NOT NULL,

                required int NOT NULL DEFAULT 3,
                rtl int NOT NULL DEFAULT 0,

                self_star bool NOT NULL DEFAULT false,
                link_edits bool NOT NULL DEFAULT true,
                link_deletes bool NOT NULL DEFAULT false,
                bots_react bool NOT NULL DEFAULT false,
                bots_on_sb bool NOT NULL DEFAULT true,

                locked bool NOT NULL DEFAULT false,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE
            )"""

        sbemoijs_table = \
            """CREATE TABLE IF NOT EXISTS sbemojis (
                id SERIAL PRIMARY KEY,
                d_id text,
                starboard_id text NOT NULL,

                name text NOT NULL,
                is_downvote bool NOT NULL DEFAULT false,

                FOREIGN KEY (starboard_id) REFERENCES starboards (id)
                    ON DELETE CASCADE
            )"""

        messages_table = \
            """CREATE TABLE IF NOT EXISTS messages (
                id text PRIMARY KEY,
                guild_id text NOT NULL,
                user_id text NOT NULL,
                orig_message_id text DEFAULT NULL,
                channel_id text NOT NULL,

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
                d_id text,
                guild_id text NOT NULL,
                user_id text NOT NULL,
                message_id text NOT NULL,

                name text NOT NULL,

                FOREIGN KEY (guild_id) REFERENCES guilds (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id)
                    ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )"""

        await self.lock.acquire()
        await self._create_table(guilds_table)
        await self._create_table(users_table)
        await self._create_table(patrons_table)
        await self._create_table(donations_table)
        await self._create_table(members_table)
        await self._create_table(starboards_table)
        await self._create_table(sbemoijs_table)
        await self._create_table(messages_table)
        await self._create_table(reactions_table)
        self.lock.release()