import os
import sys
from dotenv import load_dotenv
from quart import Quart, redirect, url_for, render_template
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


@app.route('/')
@app.route('/home')
async def home():
    stats = await app.ipc_node.request("bot_stats")
    gc, mc = stats.replace('"', '').split('-')
    return await render_template(
        'home.jinja', gcount=gc, mcount=mc
    )


@app.route('/login/')
async def login():
    return await discord.create_session(
        data={'type': 'user'}
    )


@app.route('/api/callback/')
async def callback():
    data = await discord.callback()
    if data['type'] == 'user':
        return redirect(url_for("me"))
    else:
        return redirect(url_for("servers"))


@app.route('/me/')
@requires_authorization
async def me():
    user = await discord.fetch_user()
    return await render_template('me.jinja', user=user)


@app.route('/servers/')
@requires_authorization
async def servers():
    _guilds = await discord.fetch_guilds()
    guilds = [
        g for g in _guilds if g.permissions.manage_guild
    ]
    return await render_template('dashboard.jinja', guilds=guilds)


@app.route('/servers/<int:gid>/')
@requires_authorization
async def manage_guild(gid: int):
    _guilds = await discord.fetch_guilds()
    valid_ids = [
        g.id for g in _guilds if g.permissions.manage_guild
    ]
    if gid in valid_ids:
        return await discord.create_session(
            scope=['bot'], permissions=268823632,
            data={'type': 'server'}
        )
    else:
        return redirect(url_for('servers'))


@app.errorhandler(Unauthorized)
async def handle_unauthorized(e):
    return redirect(url_for('login'))


@app.errorhandler(AccessDenied)
async def handle_denied_access(e):
    return redirect(url_for('home'))


@app.before_first_request
async def before():
    app.ipc_node = ipc


if __name__ == '__main__':
    app.run()
