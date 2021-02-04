import ast
import time
from subprocess import PIPE, run

import discord
from asyncpg.exceptions._base import InterfaceError
from discord.ext import commands, tasks

import bot_config
import checks
import functions
from cogs.stats import post_all
from database.database import Database
from paginators import disputils


def ms(t: float) -> float:
    return round(t*1000, 5)


def out(command: str) -> str:
    result = run(
        command, stdout=PIPE, stderr=PIPE,
        universal_newlines=True, shell=True
    )
    return result.stdout


class Owner(commands.Cog):
    """Owner only commands"""
    def __init__(
        self,
        bot: commands.Bot,
        db: Database
    ) -> None:
        self.db = db
        self.bot = bot
        self.dump_sqlruntimes.start()

    @tasks.loop(minutes=5)
    async def dump_sqlruntimes(self) -> None:
        async with self.bot.db.lock:
            await self.bot.db.conn.dump()

    def insert_returns(
        self,
        body
    ) -> None:
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
    async def eval_fn(
        self,
        ctx: commands.Context,
        *, body: str
    ) -> None:
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
    async def clear_global_cache(
        self,
        ctx: commands.Context
    ) -> None:
        cache = self.bot.db.cache
        cache._messages = {}
        await ctx.send("Cleared message cache for all servers.")

    @commands.command(
        name='postGuildCount', aliases=['pgc'],
        brief='Manually post the guild count to bot lists',
        description='Manually post the guild count to bot lists'
    )
    @checks.is_owner()
    async def manual_post_guild_count(
        self,
        ctx: commands.Context,
        guilds: int,
        users: int,
        bot_id: int
    ) -> None:
        async with ctx.typing():
            errors = await post_all(guilds, users, bot_id)
        string = ''
        for bl in errors:
            msg = errors[bl]
            string += f"{bl}: {msg}\n"
        await ctx.send(string)

    @commands.command(
        name='runpg', aliases=['timepg', 'timeit', 'runtime'],
        brief='Time postgres queries',
        description='Time postgres queries',
        hidden=True
    )
    async def time_postgres(
        self,
        ctx: commands.Context,
        *args: list
    ) -> None:
        if ctx.author.id in bot_config.RUN_SQL:
            result = "None"
            times = 1
            conn = self.bot.db.conn
            runtimes = []

            try:
                async with self.bot.db.lock:
                    async with conn.transaction():
                        for a in args:
                            a = ''.join(a)
                            try:
                                times = int(a)
                            except Exception:
                                start = time.time()
                                for i in range(0, times):
                                    try:
                                        result = await conn.fetch(a)
                                    except Exception as e:
                                        await ctx.send(e)
                                        raise Exception('rollback')
                                runtimes.append((time.time()-start)/times)
                                times = 1
                        raise Exception("Rollback")
            except (Exception, InterfaceError):
                pass

            for x, r in enumerate(runtimes):
                await ctx.send(f"Query {x} took {round(r*1000, 2)} ms")
            await ctx.send(result[0:500])

    @commands.command(name='sql', hidden=True)
    async def get_sql_stats(
        self,
        ctx: commands.Context,
        sort: str = 'total'
    ) -> None:
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

        def sorter(li):
            if sort == 'avg':
                return float(li[2])/li[1]
            elif sort == 'total':
                return float(li[2])
            return li[1]

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
    async def clear_sql_stats(
        self,
        ctx: commands.Context
    ) -> None:
        if ctx.message.author.id not in bot_config.RUN_SQL:
            return
        delete = \
            """DELETE FROM sqlruntimes"""

        async with self.bot.db.lock:
            async with self.bot.db.conn.transaction():
                await self.bot.db.conn.execute(delete)

        await ctx.send("Done")

    @commands.command(name='dumpnow')
    async def early_dump_sqlruntimes(
        self,
        ctx: commands.Context
    ) -> None:
        if ctx.message.author.id not in bot_config.RUN_SQL:
            return
        async with self.bot.db.lock:
            await self.bot.db.conn.dump()

        await ctx.send("Done")

    @commands.command(name='ownerclean')
    @commands.is_owner()
    async def clean_database(
        self,
        ctx: commands.Context
    ) -> None:
        """Cleans several different things from the database"""

        conn = self.bot.db.conn

        # Remove starboard messages of starboards that were deleted
        get_starboards = \
            """SELECT * FROM starboards"""
        clean_sb_messages = \
            """DELETE FROM messages
            WHERE channel_id!=ALL($1::numeric[])
            AND is_orig=False"""

        await ctx.send("Removing messages...")
        async with self.bot.db.lock:
            async with conn.transaction():
                starboards = await conn.fetch(
                    get_starboards
                )
                sids = [s['id'] for s in starboards]
                await conn.execute(clean_sb_messages, sids)

        await ctx.send("Finished cleaning")

    @commands.command(name='run')
    @commands.is_owner()
    async def run_command(
        self,
        ctx: commands.Context,
        *, command: str
    ) -> None:
        async with ctx.typing():
            output = out(command)
        if len(output) > 2000:
            output = output[0:2000] + '...'
        await ctx.send(f"```\n{output}\n```")

    @commands.command(name='reload')
    @commands.is_owner()
    async def reoloadext(
        self,
        ctx: commands.Context,
        ext: str = None
    ) -> None:
        message = (
            f"Reloaded {ext}" if ext else
            "Reloaded all extensions"
        )
        try:
            async with ctx.typing():
                if ext:
                    self.bot.reload_extension(ext)
                else:
                    for extname in self.bot.extensions:
                        self.bot.reload_extension(extname)
        except Exception as e:
            await ctx.send(f"Failed: {e}")
        else:
            await ctx.send(message)

    @commands.command(name='givemonths')
    @commands.is_owner()
    async def set_endsat(
        self,
        ctx: commands.Context,
        guild_id: int,
        months: int
    ) -> None:
        await functions.give_months(
            self.bot, guild_id, months
        )
        await ctx.send("Done")

    @commands.command(name='givecredits')
    @commands.is_owner()
    async def give_credits(
        self,
        ctx: commands.Context,
        user_id: int,
        credits: int
    ) -> None:
        await functions.givecredits(
            self.bot, user_id, credits
        )
        await ctx.send("Done")

    @commands.command(name='sudo')
    @checks.is_owner()
    async def sudo_user(
        self,
        ctx: commands.Context,
        user: discord.Member,
        command: str
    ) -> None:
        await ctx.send(f"Sudoing {user.name}...")
        ctx.message.content = command
        ctx.message.author = user
        self.bot.dispatch('message', ctx.message)


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(Owner(bot, bot.db))
