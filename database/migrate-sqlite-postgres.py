import asyncio

from discord.ext.commands import Bot
from database import Database as NewDB
from old.old_database import Database as OldDB

path_to_sql = "sql/database.sqlite3"

odb = OldDB(path_to_sql)
ndb = NewDB()
bot = Bot('!')


async def convert():
    print("Waiting...")
    await bot.wait_until_ready()
    print("Starting!")
    ocon = await odb.connect()
    oc = await ocon.cursor()
    nc = await ndb.connect()

    await oc.execute("SELECT * FROM guilds")
    guilds = await oc.fetchall()

    async with nc.transaction():
        for g in guilds:
            await ndb.q.create_guild.fetch(
                g['id']
            )
            await ndb.q.create_prefix.fetch(
                g['id'], "sb!"
            )

    await oc.execute("SELECT * FROM users")
    users = await oc.fetchall()

    async with nc.transaction():
        for u in users:
            await ndb.q.create_user.fetch(
                u['id'], bool(u['is_bot'])
            )

    await oc.execute("SELECT * FROM members")
    members = await oc.fetchall()

    async with nc.transaction():
        for m in members:
            await ndb.q.create_member.fetch(
                m['user_id'], m['guild_id']
            )
            await nc.execute(
                """UPDATE members
                SET given = $1,
                received = $2,
                xp = $3,
                lvl = $4
                WHERE user_id=$5 AND guild_id=$6""",
                m['given'], m['received'], m['xp'],
                m['lvl'], m['user_id'], m['guild_id']
            )

    await oc.execute("SELECT * FROM starboards")
    starboards = await oc.fetchall()

    async with nc.transaction():
        for s in starboards:
            await ndb.q.create_starboard.fetch(
                s['id'], s['guild_id']
            )
            await ndb.q.update_starboard.fetch(
                bool(s['self_star']), bool(s['link_edits']),
                bool(s['link_deletes']), bool(s['bots_on_sb']),
                s['required'], s['rtl'], s['id']
            )

    await oc.execute("SELECT * FROM sbemojis")
    sbemoijs = await oc.fetchall()

    async with nc.transaction():
        for se in sbemoijs:
            await ndb.q.create_sbemoji.fetch(
                se['d_id'], se['starboard_id'], se['name'],
                False
            )

    await oc.execute("SELECT * FROM messages")
    messages = await oc.fetchall()

    async with nc.transaction():
        for m in messages:
            await ndb.q.create_message.fetch(
                m['id'], m['guild_id'], m['user_id'],
                m['orig_message_id'], m['channel_id'],
                bool(m['is_orig']), bool(m['is_nsfw'])
            )

    await oc.execute("SELECT * FROM reactions")
    reactions = await oc.fetchall()

    async with nc.transaction():
        for r in reactions:
            name = r['name'] if r['d_id'] is None else str(r['d_id'])
            await ndb.q.create_reaction.fetch(
                r['guild_id'], r['user_id'], r['message_id'],
                name
            )

    print("Finished!")


@bot.event
async def on_ready():
    await convert()


async def main():
    await odb.open()
    await ndb.open(bot)
    #await bot.loop.create_task(convert())
    await bot.start(input("TOKEN: "))


loop = asyncio.get_event_loop()
loop.run_until_complete(main())
