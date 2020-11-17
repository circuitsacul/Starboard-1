import ast
import discord
import checks
import time
import bot_config
import disputils
from discord.ext import tasks

from api.post_guild_count import post_all
from discord.ext import commands


def ms(t):
    return round(t*1000, 5)


class Owner(commands.Cog):
    def __init__(self, bot, db):
        self.db = db
        self.bot = bot
        self.dump_sqlruntimes.start()

    @tasks.loop(minutes=5)
    async def dump_sqlruntimes(self):
        async with self.bot.db.lock:
            await self.bot.db.conn.dump()

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
    @checks.is_owner()
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
    @checks.is_owner()
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
    @checks.is_owner()
    async def manual_post_guild_count(
        self, ctx, guilds: int, users: int,
        bot_id
    ):
        async with ctx.typing():
            errors = await post_all(guilds, users, bot_id)
        string = ''
        for bl in errors:
            msg = errors[bl]
            string += f"{bl}: {msg}\n"
        await ctx.send(string)

    @commands.command(
        name='runpg', aliases=['timepg', 'timeit', 'rpg', 'runtime'],
        brief='Time postgres queries',
        description='Time postgres queries',
        hidden=True
    )
    async def time_postgres(self, ctx, *args):
        if ctx.author.id in bot_config.RUN_SQL:
            conn = self.bot.db.conn
            async with self.bot.db.lock:
                async with conn.transaction():
                    try:
                        async with conn.transaction():
                            for i in range(len(args)):
                                start_time = time.time()
                                no = await conn.fetch(args[i])
                                await ctx.send("Query " + str(i + 1) + " took " + str(round((time.time() - start_time) * 1000, 2)) + "ms! Here's the first 500 characters returned:")
                            raise ZeroDivisionError
                    except ZeroDivisionError:
                        await ctx.send(str(no)[:500])
                    except Exception as e:
                        await ctx.send("The query took " + str(round((time.time() - start_time) * 1000, 2)) + "ms! Here's the first 500 characters returned:")
                        await ctx.send("wow your thing errored smh **" + str(e) + "**")

    @commands.command(name='sql', hidden=True)
    async def get_sql_stats(self, ctx, sort: str = 'total'):
        if sort not in ['avg', 'total', 'count']:
            await ctx.send(
                "Valid option are: 'avg', 'total', 'count'."
                "\nDefaults to total."
            )
            return
        if ctx.message.author.id not in bot_config.RUN_SQL:
            return
        get_results = \
            """SELECT * FROM sqlruntimes"""

        def sorter(l):
            if sort == 'avg':
                return float(l[2])/l[1]
            elif sort == 'total':
                return float(l[2])
            return l[1]

        conn = self.bot.db.conn
        async with self.bot.db.lock:
            async with self.bot.db.conn.transaction():
                r = await conn.fetch(get_results)
                sorted_rows = sorted(
                    [(d['sql'], d['count'], d['time']) for d in r],
                    key=sorter, reverse=True
                )

        p = commands.Paginator(prefix='', suffix='', max_size=1000)
        embeds = []
        for sr in sorted_rows:
            p.add_line(
                f"```{sr[0]}```**{sr[1]} | {round(sr[2], 5)} seconds "
                f"| {ms(sr[2]/sr[1])} ms**"
            )

        for page in p.pages:
            e = discord.Embed(
                title='Results',
                description=page
            )
            embeds.append(e)

        ep = disputils.EmbedPaginator(self.bot, embeds)
        await ep.run([ctx.message.author], ctx.channel)

    @commands.command(name='clearsql')
    @checks.is_owner()
    async def clear_sql_stats(self, ctx):
        delete = \
            """DELETE FROM sqlruntimes"""

        async with self.bot.db.lock:
            async with self.bot.db.conn.transaction():
                await self.bot.db.conn.execute(delete)

        await ctx.send("Done")

    @commands.command(name='dumpnow')
    @checks.is_owner()
    async def early_dump_sqlruntimes(self, ctx):
        async with self.bot.db.lock:
            await self.bot.db.conn.dump()

        await ctx.send("Done")


def setup(bot):
    bot.add_cog(Owner(bot, bot.db))
