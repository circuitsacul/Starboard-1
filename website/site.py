import os
from dotenv import load_dotenv
from quart import Quart
from quart import render_template
from discord.ext.ipc import Client

load_dotenv()

app = Quart(__name__)
ipc = Client(
    'localhost', 8765,
    secret_key=os.getenv('IPC_KEY')
)


@app.route('/')
@app.route('/home')
async def home():
    gc = await app.ipc_node.request("gcount")
    return await render_template(
        'home.jinja', gcount=gc
    )


@app.before_first_request
async def before():
    app.ipc_node = ipc


if __name__ == '__main__':
    app.run()
