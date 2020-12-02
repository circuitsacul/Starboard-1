import os
import sys
from dotenv import load_dotenv
from quart import Quart, redirect, url_for, render_template, request
from quart_discord import (
    DiscordOAuth2Session,
    requires_authorization,
    Unauthorized,
    AccessDenied
)
from discord.ext.ipc import Client

sys.path.append('../')
import bot_config

load_dotenv()

app = Quart(__name__)
ipc = Client(
    'localhost', 8765,
    secret_key=os.getenv('IPC_KEY')
)
app.secret_key = os.getenv("QUART_KEY")

app.config["DISCORD_CLIENT_ID"] = bot_config.BOT_ID
app.config["DISCORD_CLIENT_SECRET"] = os.getenv("SECRET")
app.config["DISCORD_REDIRECT_URI"] = bot_config.REDIRECT_URI + '/api/callback'
app.config["DISCORD_BOT_TOKEN"] = os.getenv("TOKEN")
discord = DiscordOAuth2Session(app)

BASE_URL = 'http://127.0.0.1:5000'


async def handle_login(next: str = ''):
    return await discord.create_session(
        data={'type': 'user', 'next': next},
        scope=['identify', 'guilds']
    )


@app.route('/')
@app.route('/home/')
async def home():
    authorized = True
    user = None
    try:
        user = await discord.fetch_user()
    except Unauthorized:
        authorized = False
    stats = await app.ipc_node.request("bot_stats")
    gc, mc = stats.replace('"', '').split('-')
    return await render_template(
        'home.jinja', gcount=gc, mcount=mc,
        authorized=authorized, user=user
    )


@app.route('/login/')
async def login():
    return await handle_login()


@app.route('/logout/')
async def logout():
    discord.revoke()
    return redirect(url_for('home'))


@app.route('/api/callback/')
async def callback():
    data = await discord.callback()
    if data['type'] == 'user':
        if data['next'] == '':
            return redirect(url_for("home"))
        else:
            return redirect(BASE_URL + data['next'])
    else:
        _gid = request.args.get('guild_id')
        try:
            gid = int(_gid)
        except ValueError:
            gid = None
        if gid is None:
            return redirect(url_for("servers"))
        else:
            return redirect(url_for("manage_guild", gid=gid))


@app.route('/servers/')
@requires_authorization
async def servers():
    _guilds = await discord.fetch_guilds()
    user = await discord.fetch_user()
    guilds = [
        g for g in _guilds if g.permissions.manage_guild
    ]
    return await render_template(
        'dashboard/server-picker.jinja', guilds=guilds,
        authorized=True, user=user
    )


@app.route('/servers/<int:gid>/')
@requires_authorization
async def manage_guild(gid: int):
    _guilds = await discord.fetch_guilds()
    valid_ids = [
        g.id for g in _guilds if g.permissions.manage_guild
    ]
    if gid in valid_ids:
        resp = await app.ipc_node.request(
            'does_share', gid=gid
        )
        print(resp)
        if resp == '"1"':
            return 'yup'
        else:
            return await discord.create_session(
                scope=['bot'], permissions=268823632,
                data={'type': 'server'},
                guild_id=gid
            )
    else:
        return redirect(url_for('servers'))


@app.errorhandler(404)
async def handle_page_not_found(e):
    u = None
    a = False
    try:
        u = await discord.fetch_user()
        a = True
    except Unauthorized:
        pass
    return await render_template(
        '404.jinja', user=u, authorized=a
    ), 404


@app.errorhandler(Unauthorized)
async def handle_unauthorized(e):
    return await handle_login(next=request.path)


@app.errorhandler(AccessDenied)
async def handle_denied_access(e):
    return redirect(url_for('home'))


@app.before_first_request
async def before():
    app.ipc_node = ipc


if __name__ == '__main__':
    app.run()
