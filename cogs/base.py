import discord
import bot_config
import functions
from discord.ext import commands


pages = {
    'About Starboard': (
        "If you're looking for information on "
        "setting up the bot, skip to the next page."
        "\n\nStarboard is an open-source bot created by "
        "`Circuit#5585` with contributions from "
        "`Theelx#4980`. If you would like to support "
        "this project, you can view information with "
        "`sb!donate`."
    ),
    'General Settings/Commands': (
        "This bot allows you to have multiple "
        "custom prefixes.\n\n"
        "**sb!prefixes:**\nList all of your prefixes\n\n"
        "**sb!prefix add <prefix>:**\nAdds a prefix\n\n"
        "**sb!prefix remove <prefix>:**\n"
        "Removes a prefix\n\n"
        "**sb!random [min-stars] [#starboard]:**\n"
        "Sends a random starred message\n\n"
    ),
    'Starboard Commands': (
        "Starboards are like democratic pins. "
        "A user can vote to pin a message by "
        "reacting to it with :star:, and after "
        "reaching a certain number of stars "
        "it is sent to the starboard. "
        "\n\nTo setup Starboard, run `sb!setup`. \n"
        "Alternatively, you can use the normal commands "
        "Wich are listed on the next page.\n\n"
        "(`sb!s` is an alternative way of typing "
        "`sb!starboards`)\n\n"
        "**sb!starboards:**\nView a list of starboards\n\n"
        "**sb!starboards <channel>:**\nView the "
        "configuration for a specific starboard\n\n"
        "**sb!s add <channel>:**\nMake a channel a "
        "starboard\n\n"
        "**sb!s remove <channel>:**\nRemove a starboard "
        "\n\n"
        "**sb!s addEmoji <channel> <emoji>:**\nSet an "
        "emoji as a star emoji, which can be used to "
        "upvote messsages\n\n"
        "**sb!s removeEmoji <channel> <emoji>:**\n"
        "Remove an emoji from a starboard\n\n"
        "On the next page, there is a list of settings "
        "that can be configured either in the setup "
        "wizard or using commands."
        ""
    ),
    'Starboard Settings': (
        "Each of these settings can be configured in "
        "the setup wizard (`sb!setup`), or with the "
        "commands listed below the setting.\n\n"
        "**requiredStars:**\nHow many stars are "
        "needed for a message to appear on the "
        "starboard.\n`sb!s rs <channel> <value>`\n\n"
        "**requiredToLose:**\nHow few stars are "
        "needed before a message is removed from "
        "the starboard.\n`sb!s rtl <channel> <value>`\n\n"
        "**selfStar:**\nWether or not a user "
        "can star their own messages.\n"
        "`sb!s ss <channel> <true|false>`\n\n"
        "**linkEdits:**\nIf this is true, when the "
        "original message is edited, then the starboard "
        "message will also be edited."
        "\n`sb!s le <channel> <true|false>`\n\n"
        "**linkDeletes:**\nIf this is set to true, then "
        "if the original message is deleted, the "
        "starboard message will also also be deleted.\n"
        "`sb!s ld <channel> <true|false>`\n\n"
        "**botsOnStarboard:**\nIf this is set to false, "
        "then bot messages cannot be starred\n"
        "`sb!s bos <channel> <true|false>`"
    ),
    'AutoStar Channel Commands': (
        "AutoStar channels are channels where the "
        "bot will automatically react to messages "
        "with certain emojis (which you can set). "
        "You can also set requirements for messages "
        "to be starred, such as minimum characters "
        "(minChars), wether or not an image is required "
        "(requireImage), and wether or not to delete "
        "messages that don't meet the requirements. "
        "\n\n"
        "AutoStar channels can be setup using the "
        "setup wizard, `sb!setup`. Alternatively, you can "
        "use these commands to manage them:\n\n"
        "**sb!asc**\nView all AutoStar channels\n\n"
        "**sb!asc <channel>**\nView the configuration for "
        "an AutoStar channel\n\n"
        "**sb!asc add <channel>**\nSet a channel as an "
        "AutoStar Channel\n\n"
        "**sb!asc remove <channel>**\nRemove an AutoStar "
        "channel\n\n"
        "**sb!asc addEmoji <channel> <emoji>**\nAdd an "
        "emoji for the bot to auto react to messages with\n\n"
        "**sb!asc removeEmoji <channel> <emoji>**\nRemoves "
        "an emoji from an AutoStar channel\n\n"
        "On the next page, there is a list of configurable "
        "settings and an explanation of what they do."
    ),
    'AutoStar Channel Configuration': (
        "Each of these settings can be set in the setup "
        "wizard, or using the commands listed below "
        "the setting:\n\n"
        "**minChars**\nThe minimum number of letters/"
        "numbers in order for a message to be AutoReacted "
        "to.\n`sb!asc minChars <channel> <limit>`\n\n"
        "**requireImage**\nWhether or not messages "
        "must have an image/file attached in order "
        "to be starred.\n`sb!asc requireImage <channel> "
        "<true|false>`\n\n"
        "**deleteInvalid**\nIf this is false, messages "
        "that don't meet the requirements won't be "
        "deleted, they simply won't receive reactions. "
        "If set to true, then any messages that don't "
        "meet the requirements will be automatically "
        "deleted.\n`sb!asc deleteInvalid <channel> "
        "<true|false>`\n\n"
    ),
    'Blacklist/Whitelist': (
        "Starboard comes with an advanced blacklist/whitelist "
        "system, for both roles and channels.\n\n"
        "**sb!wl:**\nView the whitelist/blacklist "
        "configuration for all starboards\n\n"
        "**sb!wl addrole <role> <starboard>:**\n"
        "Add a role to the whitelist. Overrides any "
        "blacklisted roles\n\n"
        "**sb!wl addchannel <channel> <starboard>:**\n"
        "Adds a channel to the whitelist, and blacklists "
        "all other channels\n\n"
        "**sb!wl removerole <role> <starboard>:**\n"
        "Unwhitelists a role\n\n"
        "**sb!wl removechannel <channel> <starboard>:**\n"
        "Unwhitelists a channel\n\n"
        "**sb!bl addrole <role> <starboard>:**\n"
        "Blacklists a role, so users cannot star messages\n\n"
        "**sb!bl addchannel <channel> <starboard>:**\n"
        "Blacklists a channel, so messages there cannot "
        "be starred\n\n"
        "**sb!bl removerole <role> <starboard>:**\n"
        "Unblacklists a role\n\n"
        "**sb!bl removechannel <channel> <starboard>:**\n"
        "Unblacklists a channel\n\n"
        "This system is a bit confusing, so if you ever "
        "need help, mention me for a link to the support "
        "server."
    ),
    'Message Moderation': (
        "With this bot, you can manage messages easily.\n\n"
        "**sb!force <message id> [channel]**\n"
        "Sends a message to all starboards, regardless "
        "of the number of stars it actually has.\n\n"
        "**sb!unforce <message id> [channel]**\n"
        "Unforces a message\n\n"
        "**sb!trash <message id> [channel]**\n"
        "Trashes a message to hide it's content and prevent "
        "it from appearing on starboards\n\n"
        "**sb!untrash <message id> [channel]**\n"
        "Untrashes a message\n\n"
        "**sb!freeze <message id> [channel]**\n"
        "Prevents a message from loosing or gaining "
        "reactions\n\n"
        "**sb!unfreeze <message id> [channel]**\n"
        "Unfreezes a message\n\n"
        "**sb!frozen**\nView a list of frozen messages"
    ),
    'Starboard Premium': (
        "If you want premium perks, you must [become "
        f"a patron]({bot_config.DONATE})\n\n"
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
        f"the [support server]({bot_config.SUPPORT_SERVER})\n\n"
        "**sb!redeem <months>**\n"
        "Redeems X months of premium in "
        f"the server you use the command in. {bot_config.PREMIUM_COST}"
        " credits equals 1 month of premium for a server.\n\n"
        "**sb!premium**\nView premium info, including your "
        "current pledge and credits.\n\n"
        "**sb!guildpremium**\nView the current servers "
        "premium status.\n\n"
        "**sb!autoredeem**\nIf run in DMs, it will show you "
        "all the servers you have enabled autoredeem for. "
        "Running it in a server will just show the setting for "
        "that server.\n\n"
        "**sb!autoredeem on**\nEnables autoredeem in the server "
        "you send this command. When this is enabled, if the "
        "server is about to run out of premium it will "
        "automtically take credits from your account instead "
        "of disabling premium on the server.\n\n"
        "**sb!autoredeem off [guild id]**\nDisables autoredeem "
        "in the guild you send the command, or for the guild "
        "you sepcify."
    )
}

numer_emojis = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣"
]
stop_emoji = "⏹️"


async def showpage(
    message: discord.Message,
    embed: discord.Embed
) -> None:
    await message.edit(embed=embed)


class Base(commands.Cog):
    """Basic info about Starboard"""
    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ) -> None:
        if message.author.bot:
            return

        elif message.content.replace('!', '') == self.bot.user.mention:
            if message.guild is not None:
                await functions.check_or_create_existence(
                    self.bot, message.guild.id, message.author,
                    do_member=True
                )

            if message.guild is not None:
                p = await functions.get_one_prefix(self.bot, message.guild.id)
            else:
                p = bot_config.DEFAULT_PREFIX
            try:
                await message.channel.send(
                    f"To get started, run `{p}setup`.\n"
                    f"To see all my commands, run `{p}help`\n"
                    "If you need help, you can join the support "
                    f"server {bot_config.SUPPORT_SERVER}"
                )
            except Exception:
                pass
        else:
            await self.bot.process_commands(message)

    @commands.Cog.listener()
    async def on_ready(
        self
    ) -> None:
        await self.bot.change_presence(
            activity=discord.Game("Mention me for help")
        )
        print(
            f"Logged in as {self.bot.user.name} "
            f"in {len(self.bot.guilds)} guilds!"
        )

    @commands.command(
        name='links', aliases=['invite', 'support'],
        description='View helpful links',
        brief='View helpful links'
    )
    async def show_links(
        self,
        ctx: commands.Context
    ) -> None:
        embed = discord.Embed(title="Helpful Links", color=bot_config.COLOR)
        description = \
            f"**[Support Server]({bot_config.SUPPORT_SERVER})**"\
            f"\n**[Invite Me]({bot_config.INVITE})**"\
            f"\n**[Submit Bug Report or Suggestion]({bot_config.ISSUES_PAGE})"\
            "**"\
            f"\n**[Source Code]({bot_config.SOURCE_CODE})**"\
            f"\n**[Donate/Become a Patron]({bot_config.DONATE})**"\
            f"\n**[Vote for Starboard]({bot_config.VOTE})**"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(
        name='vote',
        description='Vote for Starboard',
        brief='Vote for Starboard'
    )
    async def show_vote_info(
        self,
        ctx: commands.Context
    ) -> None:
        embed = discord.Embed(
            title="Vote for Starboard!",
            color=bot_config.COLOR
        )
        description = \
            "If you vote for this bot, you will receive the "\
            "**@Voter** role in the **[Official Starboard Support Server]"\
            f"({bot_config.SUPPORT_SERVER}).**"\
            f"\n\n**[Click Here to Vote For Starboard!]({bot_config.VOTE})**"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(
        name='privacy', aliases=['policy'],
        description='View the bot/owners privacy policy',
        brief="View privacy policy"
    )
    async def show_privacy_policy(
        self,
        ctx: commands.Context
    ) -> None:
        embed = discord.Embed(title='Privacy Policy', color=bot_config.COLOR)
        embed.description = bot_config.PRIVACY_POLICY
        await ctx.send(embed=embed)

    @commands.command(
        name='about', brief='About Starboards',
        description='Give quick description of what a \
            starboard is and what it is for'
    )
    async def about_starboard(
        self,
        ctx: commands.Context
    ) -> None:
        msg = "Starboard is a Discord starboard bot. "\
            "Starboards are kind of like democratic pins. "\
            "A user can \"vote\" to have a message displayed on "\
            "a channel by reacting with an emoji, usually a star. "\
            "A Starboard is a great way to archive funny messages."
        embed = discord.Embed(
            title='About Starboard and Starboards',
            description=msg, color=bot_config.COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(
        name='ping', aliases=['latency'],
        description='Get various bot ping statistics.',
        brief='Get bot ping'
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def get_bot_ping(
        self,
        ctx: commands.Context
    ) -> None:
        def ms(seconds: int) -> int:
            return int((seconds*1000))

        latency = ms(self.bot.latency)

        embed = discord.Embed(
            title='Pong!',
            description=f"Average Latency: {latency} ms\n",
            color=bot_config.COLOR
        )

        other_shards = ''
        for sid, l in self.bot.latencies:
            if ctx.guild and sid == ctx.guild.shard_id:
                other_shards += f"**Shard {sid}**: {ms(l)} ms\n"
            else:
                other_shards += f"Shard {sid}: {ms(l)} ms\n"

        embed.add_field(
            name='Shards', value=other_shards
        )

        await ctx.send(embed=embed)

    @commands.command(
        name='stats', aliases=['botstats'],
        description='Bot stats', brief='Bot stats'
    )
    async def stats_for_bot(
        self,
        ctx: commands.Context
    ) -> None:
        total = 0
        for g in self.bot.guilds:
            try:
                total += g.member_count
            except AttributeError:
                pass
        embed = discord.Embed(
            title='Bot Stats', colour=bot_config.COLOR,
            description=f"**Guilds:** {len(self.bot.guilds)}"
            f"\n**Users:** {total}"
            f"\n**Ping:** {int(self.bot.latency*1000)} ms"
        )
        await ctx.send(embed=embed)

    @commands.command(
        name='help', aliases=['h', '?'],
        brief="Get help with the bot",
        description="Get help with the bot",
    )
    @commands.bot_has_permissions(send_messages=True)
    async def help(
        self,
        ctx: commands.Context
    ) -> None:
        p = ctx.prefix
        await ctx.send(
            "For a tutorial on using the bot, run "
            f"`{p}tutorial`. You can view a complete "
            f"command list with `{p}commands`, and "
            "you can get help with a specific "
            f"command by running `{p}commands <commane>`"
        )

    @commands.command(
        name='tutorial',
        description='Get help with the bot',
        brief='Get help with the bot'
    )
    @commands.bot_has_permissions(embed_links=True, send_messages=True)
    async def run_tutorial(
        self,
        ctx: commands.Context
    ) -> None:
        embeds = [
            discord.Embed(
                title=t,
                description=d,
                color=bot_config.COLOR
            ) for t, d in pages.items()
        ]
        mapping = {}
        for x, e in enumerate(embeds):
            mapping[numer_emojis[x]] = e

        contents = "Table of Contents:"
        for x, e in enumerate(embeds):
            emoji = numer_emojis[x]
            contents += f"\n{emoji}: **{e.title}**"

        running = True
        message = await ctx.send(contents)

        for emoji in mapping:
            await message.add_reaction(emoji)
        await message.add_reaction(stop_emoji)

        def check(p):
            if p.message_id != message.id:
                return False
            if p.user_id != ctx.message.author.id:
                return False
            return True

        while running:
            payload = await self.bot.wait_for(
                'raw_reaction_add', check=check
            )
            try:
                await message.remove_reaction(
                    payload.emoji.name, payload.member)
            except Exception:
                pass
            try:
                page = mapping[payload.emoji.name]
            except Exception:
                running = False
            else:
                await showpage(message, page)

        await message.edit(embed=None, content="Exited")
        try:
            await message.clear_reactions()
        except Exception:
            pass


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(Base(bot))
