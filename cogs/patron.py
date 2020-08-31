import discord, flask, functions, os, dotenv

#from flask import Response
from aiohttp import web

from discord.ext import commands
#from threading import Thread

from bot_config import COLOR, SUPPORT_SERVER_ID, PATRON_LEVELS

dotenv.load_dotenv()

DONATEBOT_TOKEN = os.getenv("DONATEBOT_TOKEN")


async def update_patron_for_user(bot, db, user_id, product_id, add: bool):
    check_patron = \
        """SELECT * FROM patrons WHERE user_id=? AND product_id=?"""
    new_patron = db.q.create_patron
    del_patron = \
        """DELETE FROM patrons WHERE id=?"""

    conn = await db.connect()
    c = await conn.cursor()
    async with db.lock:
        await c.execute(check_patron, [user_id, product_id])
        rows = await c.fetchall()
        if len(rows) == 0:
            sql_patron = None
        else:
            sql_patron = rows[0]
        if add and not sql_patron:
            await c.execute(new_patron, [user_id, product_id])
        if not add and sql_patron:
            await c.execute(del_patron, [sql_patron['id']])
        await conn.commit()
        await conn.close()

    give_role = PATRON_LEVELS[product_id]['gives_role']
    if give_role:
        await functions.handle_role(bot, db, user_id, SUPPORT_SERVER_ID, give_role, add=add)


class PatronCommands(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='patron', aliases=['donate'],
        description='View information on how you can donate and what the benefits are',
        brief='View donation info'
    )
    async def show_donate_info(self, ctx):
        embed = discord.Embed(color=COLOR, title='Patron/Donation Info')
        embed.description = \
            """Click [here](https://donatebot.io/checkout/725336160112738385) to become a patron!
            I really appreciate any support you can give me :)"""

        for level_id, level in PATRON_LEVELS.items():
            embed.add_field(
                name=level['display']['title'], value=level['display']['description']
            )

        await ctx.send(embed=embed)

    @commands.command(
        name='patronLevel', aliases=['lvl'],
        description='View a suers current patron status. User defaults to you',
        brief='View current patrons status'
    )
    async def show_patron_info(self, ctx, user: discord.Member=None):
        user_id = user.id if user else ctx.message.author.id
        levels = await functions.get_patron_levels(self.db, user_id)
        level_ids = [lvl['product_id'] for lvl in levels]
        string = "Current Patron Levels:"
        for lvl_id, lvl in PATRON_LEVELS.items():
            string += f"\n**{lvl['display']['title']}: {'Yes' if lvl_id in level_ids else 'No'}**"
        await ctx.send(string)

    @commands.command(
        name='handlePremium', aliases=['hp']
    )
    @commands.is_owner()
    async def handel_patron(self, ctx, user: discord.User=None, product_id: str=None, add: str='add'):
        if add.lower() not in ['add', 'remove', 'a', 'r']:
            await ctx.send(f"Invalid option {add}")
            return
        is_add = bool(add.lower().startswith('a'))
        if product_id is None:
            string = "Valid Products:"
            for product_id, patron_level in PATRON_LEVELS.items():
                string += f"\n**--{patron_level['display']['title']}: {product_id}**"
            await ctx.send(string)
        else:
            await update_patron_for_user(self.bot, self.db, user.id, product_id, add=is_add)
            if is_add:
                await ctx.send(f"Gave product **{product_id}** to user")
            else:
                await ctx.send(f"Removed product **{product_id}** from user")


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
                headers = request.headers
                # Check if authenticaiton token is in headers and matches token
                status = await self.handle_donation_event(data)
            except Exception as e:
                print(f"Error in donation event: {type(e)}: {e}")
                return web.Response(body="Error!", status=500)
            return web.Response(body="Caught!", status=200)

        self.app.add_routes(self.routes)

    async def handle_donation_event(self, data):
        pass


#class FlaskWebHook():
#    def __init__(self, bot, db):
#        self.bot = bot
#        self.db = db
#        self.app = flask.Flask(__name__)
#        self.queue = []
#
#        @self.app.route('/donatebot', methods=['POST'])
#        def handle_donation():
#            print("got connection")
#            data = request.get_json(silent=True)
#            token = request.headers['authorization']
#            if token != DONATEBOT_TOKEN:
#                return Response(response="Invalid Token", status=400)
#
#            purchase_id = data['product_id']
#
#            if purchase_id == "":
#                return Response(response='Ignoring Role Purchase', status=200)
#            if str(purchase_id) not in PATRON_LEVELS:
#                return Response(response="Unknown Product", status=200)
#
#            self.queue.append(data)
#
#            return Response(response="Caught :)", status=200)
#
#        self.app_thread = Thread(
#            target=self.app.run, kwargs={'port': 8080, 'host': '0.0.0.0', 'use_reloader': False, 'debug': False},
#            daemon=True
#        )
#    
#    def start(self):
#        self.app_thread.start()