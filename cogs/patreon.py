import patreon
import asyncio
from discord.ext import tasks, commands
import os

import six
from aiohttp_requests import requests

from patreon.jsonapi.parser import JSONAPIParser
from patreon.jsonapi.url_util import build_url
from patreon.utils import user_agent_string
from patreon.version_compatibility.utc_timezone import utc_timezone
from six.moves.urllib.parse import urlparse, parse_qs, urlencode


class Patreon(commands.Cog):
    """Handles interactions with Patreon"""
    def __init__(self, bot):
        self.bot = bot

        self.access_token = os.getenv("PATREON_TOKEN")
        self.client = patreon.API(self.access_token)

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


def setup(bot):
    bot.add_cog(Patreon(bot))
