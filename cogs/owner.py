import ast
import discord

from api.post_guild_count import post_all
from discord.ext import commands


class Owner(commands.Cog):
    def __init__(self, bot, db):
        self.db = db
        self.bot = bot

    def insert_returns(self, body):
        # insert return stmt if the last expression is a expression statement
        if isinstance(body[-1], ast.Expr):
            body[-1] = ast.Return(body[-1].value)
            ast.fix_missing_locations(body[-1])

        # for if statements, we insert returns into the body and the orelse
        if isinstance(body[-1], ast.If):
            self.insert_returns(body[-1].body)
            self.insert_returns(body[-1].orelse)

        # for with blocks, again we insert returns into the body
        if isinstance(body[-1], ast.With):
            self.insert_returns(body[-1].body)

    @commands.command(
        name='eval', aliases=['e']
    )
    @commands.is_owner()
    async def eval_fn(self, ctx, *, body):
        """Evaluates input.
        Input is interpreted as newline seperated statements.
        If the last statement is an expression, that is the return value.
        Usable globals:
        - `bot`: the bot instance
        - `discord`: the discord module
        - `commands`: the discord.ext.commands module
        - `ctx`: the invokation context
        - `__import__`: the builtin `__import__` function
        Such that `>eval 1 + 1` gives `2` as the result.
        The following invokation will cause the bot to send the text '9'
        to the channel of invokation and return '3' as the result of evaluating
        >eval ```
        a = 1 + 2
        b = a * 2
        await ctx.send(a + b)
        a
        ```
        """
        fn_name = "_eval_expr"

        cmd = body.strip("` ")

        # add a layer of indentation
        cmd = "\n".join(f"    {i}" for i in cmd.splitlines())

        # wrap in async def body
        body = f"async def {fn_name}():\n{cmd}"

        parsed = ast.parse(body)
        body = parsed.body[0].body

        self.insert_returns(body)

        env = {
            'bot': self.bot,
            'discord': discord,
            'ctx': ctx,
            'db': self.db,
            '__import__': __import__
        }
        exec(compile(parsed, filename="<ast>", mode="exec"), env)

        result = (await eval(f"{fn_name}()", env))
        await ctx.send(result)

    @commands.command(
        name='globalClearCache', aliases=['gcc'],
        brief='Clear cache from all servers',
        description='Clear cache from all servers'
    )
    @commands.is_owner()
    async def clear_global_cache(self, ctx):
        cache = self.bot.db.cache
        async with cache.lock:
            cache._messages = {}
        await ctx.send("Cleared message cache for all servers.")

    @commands.command(
        name='postGuildCount', aliases=['pgc'],
        brief='Manually post the guild count to bot lists',
        description='Manually post the guild count to bot lists'
    )
    @commands.is_owner()
    async def manual_post_guild_count(
        self, ctx, guilds: int, users: int,
        bot_id
    ):
        async with ctx.typing():
            errors = post_all(guilds, users, bot_id)
        await ctx.send(errors)
