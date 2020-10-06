import pickle, asyncio, database
from discord.ext.commands import Bot
from aiosqlite import Error
from emoji import UNICODE_EMOJI

PICKLE_FILE = "db.pickle"
SQL_FILE = 'sql/converted.sqlite3'

TOKEN = "redacted"

bot = Bot(command_prefix='!')
db = database.Database(SQL_FILE)

with open(PICKLE_FILE, 'rb') as pf:
    data = pickle.load(pf)


def is_emoji(s):
    return s in UNICODE_EMOJI


def get_emoji(string):
    try:
        return int(string)
    except ValueError:
        if is_emoji(string):
            return string
        return None


async def convert():
    await bot.wait_until_ready()

    conn = await db.connect()
    c = await conn.cursor()

    # Guilds and users
    for user in bot.users:
        await c.execute(
            db.q.create_user,
            [user.id, user.bot]
        )

    for guild in bot.guilds:
        await c.execute(db.q.create_guild, [guild.id])

        for member in guild.members:
            await c.execute(
                db.q.create_member,
                [member.id, guild.id]
            )

    # Actual database
    used_message_ids = []

    total_len = 0

    for guild_id in data['guilds']:
        if guild_id not in [g.id for g in bot.guilds]:
            continue

        for channel_id, message_id in data['guilds'][guild_id]['messages']:
            total_len += 1
            if message_id in used_message_ids:
                continue
            used_message_ids.append(message_id)

            dict_msg = data['guilds'][guild_id]['messages'][(channel_id, message_id)] # dict(emojis, links, author)

            try:
                dict_msg['author']
            except KeyError:
                continue

            try:
                await c.execute(
                    db.q.create_message,
                    [
                        message_id, guild_id, dict_msg['author'],
                        None, channel_id, True, False
                    ]
                )
            except Error:
                pass
            else:
                for _emoji in dict_msg['emojis']:
                    dict_reaction = dict_msg['emojis'][_emoji]
                    emoji = get_emoji(_emoji)
                    if emoji is None:

                    for user_id in dict_reaction:
                        try:
                            await c.execute(
                                db.q.create_reaction,
                                [
                                    guild_id, user_id, message_id, str(emoji)
                                ]
                            )
                        except:
                            pass

        for starboard_id in data['guilds'][guild_id]['channels']:
            starboard = data['guilds'][guild_id]['channels'][starboard_id]
            le = starboard['link_edits']
            ld = starboard['link_deletes']
            ss = starboard['self_star']
            rs = starboard['required_stars']
            rtl = starboard['required_to_lose']
            emojis = starboard['emojis']
            messages = starboard['messages']

            await c.execute(
                db.q.create_starboard,
                [starboard_id, guild_id]
            )
            await c.execute(
                db.q.update_starboard,
                [
                    ss, le, ld, False, True, rs, rtl, starboard_id
                ]
            )

            for _emoji in emojis:
                emoji = get_emoji(_emoji)
                if emoji is None:
                    continue

                try:
                    await c.execute(
                        db.q.create_sbemoji,
                        [
                            emoji if type(emoji) is int else None,
                            starboard_id, str(emoji), False
                        ]
                    )
                except:
                    pass

            for starboard_message in messages:
                orig_ch_id, orig_msg_id = messages[starboard_message]

                try:
                    await c.execute(
                        db.q.create_message,
                        [
                            starboard_message, guild_id, 700796664276844612,
                            orig_msg_id, starboard_id, False, False
                        ]
                    )
                except:
                    pass

    await conn.commit()
    await conn.close()


async def main():
    await db.open()
    bot.loop.create_task(convert())
    await bot.start(TOKEN)


loop = asyncio.get_event_loop()
loop.run_until_complete(main())