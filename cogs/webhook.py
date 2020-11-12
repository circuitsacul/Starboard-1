from aiohttp import web
import os
import bot_config

HOOK_AUTH = os.getenv("TOP_HOOK_AUTH")


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
        #@self.routes.post('/webhook')
        #async def donation_event(request):
        #    try:
        #        data = await request.json()
        #        if request.headers['authorization'] != DONATEBOT_TOKEN:
        #            return web.Response(body='Error!', status=500)
        #        else:
        #            _ = await self.handle_donation_event(data)  # stats
        #    except Exception as e:
        #        print(f"Error in donation event: {type(e)}: {e}")
        #        return web.Response(body="Error!", status=500)
        #    return web.Response(body="Caught!", status=200)

        @self.routes.post('/dblvote')
        async def vote(request):
            if request.headers['authorization'] != HOOK_AUTH:
                return web.Response(body='Invalid Token', status=500)

            data = await request.json()
            if data['type'] == 'test':
                print("Test Worked:")
                print(data)
            else:
                user_id = int(data['user'])
                channel = self.bot.get_channel(bot_config.VOTE_LOG_ID)
                if channel is not None:
                    await channel.send(
                        f"<@{user_id}> voted for Starboard!"
                    )
                print(f"User {data['user']} voted!")

            return web.Response(body='Vote caught', status=200)

        @self.routes.get('')
        async def ping(request):
            return web.Response(body="I'm Here!", status=200)

        self.app.add_routes(self.routes)

    #async def handle_donation_event(self, data):
    #    product_id = None if 'product_id' not in data else data['product_id']
    #    role_id = None if 'role_id' not in data else data['role_id']
    #    async with self.db.lock:
    #        conn = await self.db.connect()
    #        async with conn.transaction():
    #            await conn.execute(
    #                self.db.q.create_donation,
    #                data['txn_id'], data['buyer_id'], product_id, role_id,
    #                data['guild_id'], data['buyer_email'], data['price'],
    #                data['currency'], data['recurring'], data['status']
    #            )
#
#        if 'product_id' not in data:
#            pass
#        else:
#            add = True if data['status'] == 'completed' else False
#            update_patron_for_user(
#                self.bot, self.db, data['buyer_id'], data['product_id'], add
#            )
