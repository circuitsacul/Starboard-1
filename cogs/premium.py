import asyncio
import discord
import bot_config
import functions
import datetime
import humanize
from discord.ext import tasks, commands
import os

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

    @tasks.loop(minutes=1)
    async def update_patrons(self):
        print("Updating patrons...")
        all_patrons = await self.get_all_patrons()
        print(f"Patrons: {all_patrons}")

    @tasks.loop(hours=1)
    async def check_expired_premium(self):
        print("Checking for expired premium")
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
                print("Found expired")
                async with self.bot.db.lock:
                    async with conn.transaction():
                        await conn.execute(
                            expire_prem, sg['id']
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
        natural_endsat = humanize.naturalday(endsat)
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
            "To gain more, you must [become "
            f"a patron]({bot_config.DONATE}) or "
            f"[donate](https://donatebot.io/checkout/725336160112738385)\n\n"
            "To make things as simple as possible, we use a "
            "credit system for premium. It works much like "
            "discord boosts -- every $ you send to us gives "
            "you 1 premium credit, and once you have "
            f"{bot_config.PREMIUM_COST} "
            "credits you can convert that to 1 month "
            "of premium for 1 server. You can gain credits "
            "by donating, or by becoming a patron (which will "
            "give you X credits/month, depending on your tier).\n\n"
            "If you ever have any questions feel free to join "
            f"the [support server]({bot_config.SUPPORT_SERVER})"
        ) if not is_patron else (
            "Thanks for being a patron! It would appear you "
            f"are paying ${payment}/month, so you get "
            f"{payment} credits every month.\n\n"
            f"You currently have **{credits}** credits."
        )
        if is_patron:
            embed.add_field(
                name='Perks',
                value=bot_config.PREMIUM_DISPLAY
            )

        await ctx.send(embed=embed)


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
