import discord
import functions
import os
import dotenv
import bot_config
import checks
from aiohttp import web
from discord.ext import commands

from bot_config import COLOR, SUPPORT_SERVER_ID, PATRON_LEVELS

dotenv.load_dotenv()

DONATEBOT_TOKEN = os.getenv("DONATEBOT_TOKEN")
HOOK_AUTH = os.getenv("TOP_HOOK_AUTH")


async def update_patron_for_user(bot, db, user_id, product_id, add: bool):
    check_patron = \
        """SELECT * FROM patrons WHERE user_id=$1 AND product_id=$2"""
    new_patron = db.q.create_patron
    del_patron = \
        """DELETE FROM patrons WHERE id=$1"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            rows = await conn.fetch(check_patron, user_id, product_id)
            if len(rows) == 0:
                sql_patron = None
            else:
                sql_patron = rows[0]
            if add and not sql_patron:
                await new_patron.fetch(user_id, product_id)
            if not add and sql_patron:
                await conn.execute(del_patron, sql_patron['id'])

    give_role = PATRON_LEVELS[product_id]['gives_role']
    if give_role:
        try:
            await functions.handle_role(
                bot, db, user_id, SUPPORT_SERVER_ID, give_role, add=add
            )
        except AttributeError:
            pass


class PatronCommands(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(name='donationevents', aliases=['de'])
    @checks.is_owner()
    async def list_donation_events(self, ctx):
        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                donations = await conn.fetch("SELECT * FROM donations")
        string = None
        if len(donations) == 0:
            string = "No Donations Yet"
        else:
            string = ""
            for d in donations:
                pid = d['product_id'] or d['role_id']
                string += f"<@{d['user_id']}> {d['status']} purchase of "
                string += f"**{pid}**\n"
        await ctx.send(string)

    @commands.command(
        name='patron', aliases=['donate'],
        description='View information on how you can donate and what the '
        'benefits are',
        brief='View donation info'
    )
    async def show_donate_info(self, ctx):
        embed = discord.Embed(color=COLOR, title='Patron/Donation Info')
        embed.description = f"Click [here]({bot_config.DONATE})"\
            "to become a patron!"\
            "I really appreciate any support you can give me :)"

        for level_id, level in PATRON_LEVELS.items():
            embed.add_field(
                name=level['display']['title'], value=level['display']
                ['description']
            )

        await ctx.send(embed=embed)

    @commands.command(
        name='patronLevel', aliases=['lvl', 'pl'],
        description='View a suers current patron status. User defaults to you',
        brief='View current patrons status'
    )
    async def show_patron_info(
        self, ctx, user: discord.Member = None
    ):
        user = user if user else ctx.message.author
        user_id = user.id
        levels = await functions.get_patron_levels(self.db, user_id)
        level_ids = [lvl['product_id'] for lvl in levels]
        title = f"Current Patron Levels for **{user}**:"
        string = ''
        for lvl_id, lvl in PATRON_LEVELS.items():
            string += f"\n**{lvl['display']['title']}: "\
                f"{'Yes' if lvl_id in level_ids else 'No'}**"

        embed = discord.Embed(
            title=title, description=string, color=bot_config.COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(
        name='handlePremium', aliases=['hp']
    )
    @checks.is_owner()
    async def handel_patron(
        self, ctx, user: discord.User = None,
        product_id: str = None, add: str = 'add'
    ):
        if add.lower() not in ['add', 'remove', 'a', 'r']:
            await ctx.send(f"Invalid option {add}")
            return
        is_add = bool(add.lower().startswith('a'))
        if product_id is None:
            string = "Valid Products:"
            for product_id, patron_level in PATRON_LEVELS.items():
                string += f"\n**--{patron_level['display']['title']}: "\
                    f"{product_id}**"
            await ctx.send(string)
        else:
            await update_patron_for_user(
                self.bot, self.db, user.id, product_id, add=is_add
            )
            if is_add:
                await ctx.send(f"Gave product **{product_id}** to {user}")
            else:
                await ctx.send(f"Removed product **{product_id}** from {user}")


class HttpWebHook():
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db
        self.routes = web.RouteTableDef()
        self.app = web.Application()
        self._set_routes()

        self.runner = web.AppRunner(self.app)

    async def start(self):
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', 8080)
        await self.site.start()

    async def close(self):
        await self.runner.cleanup()

    def _set_routes(self):
        @self.routes.post('/webhook')
        async def donation_event(request):
            try:
                data = await request.json()
                if request.headers['authorization'] != DONATEBOT_TOKEN:
                    return web.Response(body='Error!', status=500)
                else:
                    _ = await self.handle_donation_event(data)  # stats
            except Exception as e:
                print(f"Error in donation event: {type(e)}: {e}")
                return web.Response(body="Error!", status=500)
            return web.Response(body="Caught!", status=200)

        @self.routes.post('/dblvote')
        async def vote(request):
            print(await request.json)

        @self.routes.get('')
        async def ping(request):
            return web.Response(body="I'm Here!", status=200)

        self.app.add_routes(self.routes)

    async def handle_donation_event(self, data):
        product_id = None if 'product_id' not in data else data['product_id']
        role_id = None if 'role_id' not in data else data['role_id']
        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                await conn.execute(
                    self.db.q.create_donation,
                    data['txn_id'], data['buyer_id'], product_id, role_id,
                    data['guild_id'], data['buyer_email'], data['price'],
                    data['currency'], data['recurring'], data['status']
                )

        if 'product_id' not in data:
            pass
        else:
            add = True if data['status'] == 'completed' else False
            update_patron_for_user(
                self.bot, self.db, data['buyer_id'], data['product_id'], add
            )
