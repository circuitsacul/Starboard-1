import os
import sys
from dotenv import load_dotenv
from quart import Quart, redirect, url_for, render_template
from quart_discord import (
    DiscordOAuth2Session,
    requires_authorization,
    Unauthorized
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
app.config["DISCORD_REDIRECT_URI"] = bot_config.REDIRECT_URI
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
    return await discord.create_session()


@app.route('/callback/')
async def callback():
    await discord.callback()
    return redirect(url_for("me"))


@app.route('/me/')
@requires_authorization
async def me():
    user = await discord.fetch_user()
    return f"""
    <html>
        <head>
            <title>{user.name}</title>
        </head>
        <body>
            <img src='{user.avatar_url}' />
        </body>
    </html>"""


@app.errorhandler(Unauthorized)
async def handle_unauthorized(e):
    return redirect(url_for('login'))


@app.before_first_request
async def before():
    app.ipc_node = ipc


if __name__ == '__main__':
    app.run()
