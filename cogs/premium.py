import asyncio
import discord
import bot_config
import functions
import datetime
import humanize
import os
from discord.ext import tasks, commands

from paginators import disputils

from aiohttp_requests import requests

from patreon.schemas import campaign
from patreon.jsonapi.parser import JSONAPIParser
from patreon.jsonapi.url_util import build_url
from patreon.utils import user_agent_string
from patreon.version_compatibility.utc_timezone import utc_timezone
from six.moves.urllib.parse import urlparse, parse_qs, urlencode


class Premium(commands.Cog):
    """Premium related commands"""
    def __init__(self, bot):
        self.bot = bot

        self.access_token = os.getenv("PATREON_TOKEN")
        self.client = API(self.access_token)

        self.update_patrons.start()
        self.check_expired_premium.start()
        self.do_payroll.start()

    @tasks.loop(minutes=1)
    async def update_patrons(self):
        update_user = \
            """UPDATE users
            SET payment=$1
            WHERE id=$2"""
        get_user = \
            """SELECT * FROM users
            WHERE id=$1"""
        get_sql_patrons = \
            """SELECT * FROM users
            WHERE payment != 0"""

        all_patrons = await self.get_all_patrons()
        all_patron_ids = [
            p['discord_id']
            for p in all_patrons
            if p['discord_id'] is not None
        ]
        conn = self.bot.db.conn
        for patron in all_patrons:
            if patron['discord_id'] is None:
                await functions.alert_owner(
                    self.bot, f"{patron} has no discord id")
                continue
            if patron['declined'] is True:
                await functions.alert_owner(
                    self.bot, f"{patron} was declined")
                continue
            user = await self.bot.fetch_user(int(patron['discord_id']))
            await functions.check_or_create_existence(
                self.bot, user=user
            )
            async with self.bot.db.lock:
                async with conn.transaction():
                    suser = await conn.fetchrow(
                        get_user, patron['discord_id']
                    )
            if suser['payment'] != patron['payment']:
                async with self.bot.db.lock:
                    async with conn.transaction():
                        await conn.execute(
                            update_user, patron['payment'],
                            patron['discord_id']
                        )

                if suser['payment'] == 0:
                    await functions.givecredits(
                        self.bot, int(suser['id']),
                        patron['payment']
                    )

                text = (
                    "Thanks for becoming a patron! You "
                    f"have received {patron['payment']} "
                    "credits, which can be redeemed "
                    "for premium (see `sb!premium` for "
                    "more info)."
                ) if suser['payment'] == 0 else (
                    "Looks like you downgraded to "
                    f"${patron['payment']}/month. You "
                    f"have just now received {patron['payment']} "
                    "credits, you will receive that much "
                    "every month from now on."
                ) if suser['payment'] > patron['payment'] else (
                    "Looks like you upgraded to "
                    f"${patron['payment']}/month! "
                    "You have just no received "
                    f"{patron['payment']} credits, "
                    "and you will receive that much "
                    "every month from now on."
                )
                try:
                    await functions.alert_user(
                        self.bot, patron['discord_id'], text
                    )
                except Exception as e:
                    await functions.alert_owner(e)

        # Check any removed patrons
        removed = []
        async with self.bot.db.lock:
            async with conn.transaction():
                sql_all_patrons = await conn.fetch(
                    get_sql_patrons
                )
                for u in sql_all_patrons:
                    if int(u['id']) not in all_patron_ids:
                        await conn.execute(
                            update_user, 0, u['id']
                        )
                        removed.append(int(u['id']))
        for uid in removed:
            try:
                await functions.alert_user(
                    self.bot, uid,
                    "It looks like you removed your pledge. "
                    "We're sorry to see you go, but we "
                    "are very grateful for all the support "
                    "you've given us in the past!"
                )
            except Exception as e:
                await functions.alert_owner(e)

    @tasks.loop(minutes=10)
    async def do_payroll(self):
        get_latest_payroll = \
            """SELECT MAX (paydate) FROM payrolls"""
        create_payroll = \
            """INSERT INTO payrolls VALUES ($1)"""

        conn = self.bot.db.conn
        now = datetime.datetime.now()
        async with self.bot.db.lock:
            async with conn.transaction():
                last_date = await conn.fetchval(
                    get_latest_payroll
                )
                await conn.execute(create_payroll, now)

        if last_date.month != now.month:
            await functions.do_payroll(self.bot)

    @tasks.loop(minutes=1)
    async def check_expired_premium(self):
        get_premium_guilds = \
            """SELECT * FROM guilds WHERE
            premium_end is not NULL"""
        expire_prem = \
            """UPDATE guilds
            SET premium_end=NULL
            WHERE id=$1"""

        conn = self.bot.db.conn
        async with self.bot.db.lock:
            async with conn.transaction():
                sql_prem_guilds = await conn.fetch(
                    get_premium_guilds
                )

        now = datetime.datetime.now()

        for sg in sql_prem_guilds:
            if sg['premium_end'] < now:
                # Premium for this guild has expired
                did_redeem = await functions.autoredeem(
                    self.bot, int(sg['id'])
                )
                if did_redeem is True:
                    continue

                async with self.bot.db.lock:
                    async with conn.transaction():
                        await conn.execute(
                            expire_prem, sg['id']
                        )
                await functions.refresh_guild_premium(
                    self.bot, int(sg['id'])
                )

    async def get_all_patrons(self):
        """Get the list of all patrons
        --
        @return list"""

        # If the client doesn't exist
        if self.client is None:
            print("Error : Patron API client not defined")
            return

        patrons = []

        # Get the campaign id
        campaign_resource = await self.client.fetch_campaign()
        campaign_id = campaign_resource.data()[0].id()

        # Get all the pledgers
        all_pledgers = []    # Contains the list of all pledgers
        cursor = None  # Allows us to walk through pledge pages
        stop = False

        while not stop:
            # Get the resources of the current pledge page
            # Each page contains 25 pledgers, also
            # fetches the pledge info such as the total
            # $ sent and the date of pledge end
            pledge_resource = await self.client.fetch_page_of_pledges(
                campaign_id, 25,
                cursor=cursor,
                fields={
                    "pledge": [
                        "total_historical_amount_cents",
                        "declined_since"
                    ]
                }
            )

            # Update cursor
            cursor = await self.client.extract_cursor(pledge_resource)

            # Add data to the list of pledgers
            all_pledgers += pledge_resource.data()

            # If there is no more page, stop the loop
            if not cursor:
                stop = True
                break

        # Get the pledgers info and add the premium status
        for pledger in all_pledgers:
            await asyncio.sleep(0)

            payment = 0
            total_paid = 0
            is_declined = False

            # Get the date of declined pledge
            # False if the pledge has not been declined
            declined_since = pledger.attribute("declined_since")
            total_paid = pledger.attribute("total_historical_amount_cents")/100

            # Get the pledger's discord ID
            try:
                discord_id = int(pledger.relationship("patron").attribute(
                    "social_connections")["discord"]["user_id"])
            except Exception:
                discord_id = None

            # Get the reward tier of the player
            if pledger.relationships()["reward"]["data"]:
                payment = int(pledger.relationship(
                    "reward").attribute("amount_cents") / 100)

            # Check if the patron has declined his pledge
            if declined_since is not None:
                is_declined = True

            # Add patron data to the patrons list
            patrons.append(
                {
                    "name": pledger.relationship("patron").attribute(
                        "first_name"),
                    "payment": int(payment),
                    "declined": is_declined,
                    "total": int(total_paid),
                    "discord_id": discord_id
                }
            )

        return patrons

    @commands.command(name='patrons')
    @commands.is_owner()
    async def get_patrons(self, ctx):
        await ctx.send(await self.get_all_patrons())

    @commands.command(
        name='guildPremium', aliases=['serverPremium'],
        breif="View server premium status"
    )
    @commands.guild_only()
    async def get_guild_premium(self, ctx):
        """Shows the premium status of the current
        guild/server"""
        endsat = await functions.get_prem_endsat(
            self.bot, ctx.guild.id
        )
        now = datetime.datetime.now()
        if endsat:
            natural_endsin = humanize.naturaldelta(endsat-now)
        else:
            natural_endsin = None
        natural_endsat = humanize.naturaldate(endsat)
        description = (
            "It looks like this server doesn't have "
            "premium yet. Somone with premium credits "
            "must use the `redeem` command here to give "
            "it premium!"
        ) if endsat is None else (
            f"This server has premium until {natural_endsat}, "
            f"which is {natural_endsin} from now."
        )
        embed = discord.Embed(
            title="Server Premium Status",
            description=description,
            color=bot_config.COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(
        name='premium', aliases=['donate', 'patron', 'credits'],
        description='View information on how you can donate and what the '
        'benefits are',
        brief='View donation info'
    )
    async def show_donate_info(self, ctx):
        embed = discord.Embed(
            color=bot_config.COLOR, title='Premium Info'
        )
        is_patron, payment = await functions.is_patron(
            self.bot, ctx.message.author.id
        )
        credits = await functions.get_credits(
            self.bot, ctx.message.author.id
        )
        embed.description = (
            f"You have **{credits}** credits.\n"
            + ("Redeem them with `sb!redeem`\n" if credits > 0 else '')
            + "\nTo make things as simple as possible, we use a "
            "credit system for premium. It works much like "
            "discord boosts -- every $ you send to us gives "
            "you 1 premium credit, and once you have "
            f"{bot_config.PREMIUM_COST} "
            "credits you can convert that to 1 month "
            "of premium for 1 server. You can gain credits "
            "by donating, or by becoming a patron (which will "
            "give you X credits/month, depending on your tier).\n\n"
            "If you ever have any questions, feel free to join "
            f"the [support server]({bot_config.SUPPORT_SERVER})."
        ) + (
            "\n\nTo gain more credits, you can donate or "
            f"[become a patron]({bot_config.DONATE})."
            if not is_patron else ''
        )
        if not is_patron:
            embed.add_field(
                name='Perks',
                value=bot_config.PREMIUM_DISPLAY
            )

        await ctx.send(embed=embed)

    @commands.command(
        name='redeem',
        brief="Redeems premium on a server"
    )
    async def redeem_premium(
        self, ctx,
        months: int
    ) -> None:
        """Spend some of your credits to give
        the current server premium.

        <months>: A required argument for the
        number of months to give the current
        server."""
        prem_cost = bot_config.PREMIUM_COST
        p = disputils.Confirmation(
            self.bot, bot_config.COLOR
        )
        if await p.confirm(
            "Are you sure? This will cost you "
            f"{prem_cost*months} credits and will "
            f"give {ctx.guild.name} {months} months "
            "of premium.", ctx.message.author,
            channel=ctx.channel
        ) is True:
            try:
                await functions.redeem(
                    self.bot, ctx.message.author.id,
                    ctx.guild.id, months
                )
            except Exception as e:
                print(type(e), e)
                await p.quit(str(e))
            else:
                new_endsat = humanize.naturaldate(
                    await functions.get_prem_endsat(
                        self.bot, ctx.guild.id
                    )
                )
                await p.quit(
                    f"You have spent {months*prem_cost} "
                    f"credits, and {ctx.guild.name} now "
                    f"has premium until {new_endsat}"
                )
        else:
            await p.quit("Cancelled.")

    @commands.group(
        name='autoredeem', aliases=['ar'],
        brief="View+Manage autoredeem for servers",
        invoke_without_command=True
    )
    async def autoredeem(
        self, ctx
    ) -> None:
        """View and manage autoredeem settings. Running
        this command with no arguments will show the
        setting for the current server you are in. If you
        run it in DMs, it will list all servers that
        autoredeem is on for.
        """
        conn = self.bot.db.conn

        if ctx.guild is None:  # used in DMs
            async with self.bot.db.lock:
                async with conn.transaction():
                    ar_members = await conn.fetch(
                        """SELECT * FROM members
                        WHERE user_id=$1
                        AND autoredeem=True""",
                        ctx.message.author.id
                    )
            if len(ar_members) > 0:
                description = "AutoRedeem is on for these servers:"
                for m in ar_members:
                    guild = self.bot.get_guild(int(m['guild_id']))
                    description += f"\n{guild.name} `{guild.id}`"
                embed = discord.Embed(
                    title='AutoRedeem',
                    description=description,
                    color=bot_config.COLOR
                )
                await ctx.send(embed=embed)
            else:
                await ctx.send(
                    "You have not enabled AutoRedeem on any servers."
                )
        else:
            async with self.bot.db.lock:
                async with conn.transaction():
                    is_on = await conn.fetchval(
                        """SELECT autoredeem FROM members
                        WHERE user_id=$1 AND guild_id=$2""",
                        ctx.message.author.id, ctx.guild.id
                    )
            await ctx.send(
                "You have not enabled autoredeem on this server." if not is_on
                else "You have enabled autoredeem on this server."
            )

    @autoredeem.command(
        name='enable', aliases=['on'],
        brief='Enables autoredeem on a server'
    )
    @commands.guild_only()
    async def enable_autoredeem(
        self, ctx
    ) -> None:
        """Enables AutoRedeem on the current server, so the next
        time it is out of premium it will automatically
        redeem credits from your account."""
        conn = self.bot.db.conn

        async with self.bot.db.lock:
            async with conn.transaction():
                already_on = await conn.fetchrow(
                    """SELECT * FROM members
                    WHERE guild_id=$1
                    AND autoredeem=True""",
                    ctx.guild.id
                ) is not None
                already_ar = await conn.fetchrow(
                    """SELECT * FROM members
                    WHERE guild_id=$1
                    AND user_id=$2
                    AND autoredeem=True""",
                    ctx.guild.id,
                    ctx.message.author.id
                ) is not None

        if already_ar:
            await ctx.send("You already have autoredeem enabled here.")
            return

        c = disputils.Confirmation(self.bot, bot_config.COLOR)
        await c.confirm(
            "Are you sure? This will automatically "
            "take credits out of your account when "
            "this server runs out of premium!"
            + (
                "\n\nAlso, someone else has already "
                "enabled autoredeem for this server. "
                "You can still enable it for yourself, though."
                if already_ar else ''
            ),
            ctx.message.author, ctx.channel
        )

        if not c.confirmed:
            await c.quit("Cancelled")
            return

        async with self.bot.db.lock:
            async with conn.transaction():
                await conn.execute(
                    """UPDATE members
                    SET autoredeem=True
                    WHERE user_id=$1
                    AND guild_id=$2""",
                    ctx.message.author.id,
                    ctx.guild.id
                )
        await c.quit("AutoRedeem has been enabled!")

    @autoredeem.command(
        name='disable', aliases=['off'],
        brief="Disables autoredeem for a server"
    )
    async def disable_autoredeem(
        self, ctx, guild_id: int = None
    ) -> None:
        """Disables autoredeem for a specific server.

        [guild_id]: The id of the server you want to
        disable AutoRedeem for. An optional argument.
        Required if you run it in DMs, otherwise it defaults
        to the server you run it in.
        """

        if ctx.guild is None and guild_id is None:
            await ctx.send(
                "Please either specify a server id, or "
                "run this command in the server you want "
                "to disable AutoRedeem on."
            )
            return

        guild = self.bot.get_guild(778289112381784115)

        conn = self.bot.db.conn

        async with self.bot.db.lock:
            async with conn.transaction():
                await conn.execute(
                    """UPDATE members
                    SET autoredeem=False
                    WHERE user_id=$1
                    AND guild_id=$2""",
                    ctx.message.author.id,
                    guild_id or ctx.guild.id
                )

        await ctx.send(f"AutoRedeem has been disabled on {guild.name}")


# I stole this from the patreon lib and converted to async
class API(object):
    def __init__(self, access_token):
        super(API, self).__init__()
        self.access_token = access_token

    async def fetch_user(self, includes=None, fields=None):
        return await self.__get_jsonapi_doc(
            build_url('current_user', includes=includes, fields=fields)
        )

    async def fetch_campaign_and_patrons(self, includes=None, fields=None):
        if not includes:
            includes = campaign.default_relationships \
                + [campaign.Relationships.pledges]
        return await self.fetch_campaign(includes=includes, fields=fields)

    async def fetch_campaign(self, includes=None, fields=None):
        return await self.__get_jsonapi_doc(
            build_url(
                'current_user/campaigns', includes=includes, fields=fields
            )
        )

    async def fetch_page_of_pledges(
            self, campaign_id, page_size, cursor=None, includes=None,
            fields=None
    ):
        url = 'campaigns/{0}/pledges'.format(campaign_id)
        params = {'page[count]': page_size}
        if cursor:
            try:
                cursor = self.__as_utc(cursor).isoformat()
            except AttributeError:
                pass
            params.update({'page[cursor]': cursor})
        url += "?" + urlencode(params)
        return await self.__get_jsonapi_doc(
            build_url(url, includes=includes, fields=fields)
        )

    @staticmethod
    async def extract_cursor(jsonapi_document, cursor_path='links.next'):
        def head_and_tail(path):
            if path is None:
                return None, None
            head_tail = path.split('.', 1)
            return head_tail if len(head_tail) == 2 else (head_tail[0], None)

        if isinstance(jsonapi_document, JSONAPIParser):
            jsonapi_document = jsonapi_document.json_data

        head, tail = head_and_tail(cursor_path)
        current_dict = jsonapi_document
        while head and type(current_dict) == dict and head in current_dict:
            current_dict = current_dict[head]
            head, tail = head_and_tail(tail)

        # Path was valid until leaf, at which point nothing was found
        if current_dict is None or (head is not None and tail is None):
            return None
        # Path stopped before leaf was reached
        elif current_dict and type(current_dict) != str:
            raise Exception(
                'Provided cursor path did not result in a link', current_dict
            )

        link = current_dict
        query_string = urlparse(link).query
        parsed_query_string = parse_qs(query_string)
        if 'page[cursor]' in parsed_query_string:
            return parsed_query_string['page[cursor]'][0]
        else:
            return None

    # Internal methods
    async def __get_jsonapi_doc(self, suffix):
        response_json = await self.__get_json(suffix)
        if response_json.get('errors'):
            return response_json
        return JSONAPIParser(response_json)

    async def __get_json(self, suffix):
        response = await requests.get(
            "https://www.patreon.com/api/oauth2/api/{}".format(suffix),
            headers={
                'Authorization': "Bearer {}".format(self.access_token),
                'User-Agent': user_agent_string(),
            }
        )
        return await response.json()

    @staticmethod
    def __as_utc(dt):
        if hasattr(dt, 'tzinfo'):
            if dt.tzinfo:
                return dt.astimezone(utc_timezone())
            else:
                return dt.replace(tzinfo=utc_timezone())
        return dt


def setup(bot):
    bot.add_cog(Premium(bot))
