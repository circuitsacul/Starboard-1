## About Starboard

Starboard is an advanced, reliable, and highly customizable starboard bot, allowing for multiple starboards, multiple emojis, auto-star channels, and much more coming!

  

This documentation gives you a quick start to using the bot. If you see a problem, please let me know, either by using the bots suggest command or joining the support server. My discord username is `@Circuit#5585`.

  

## Useful Links

[Click here for a demonstration](https://drive.google.com/file/d/1fMx3cTMYGtpgWtW-ZrovJL3nOFBBQrzu/view?usp=sharing)

  

[Invite Starboard to your server](https://dsc.gg/starboard)

  

[Join the support server](https://discord.gg/3gK8mSA)

  

[Starboard Documentation/Wiki](https://github.com/CircuitsBots/Starboard/wiki)

  

## Starboard's Features

- Supports multiple starboards

- Advanced Channel/Role Whitlisting/Blacklisting

- AutoStar Channels (media channels)

- Supports multiple normal and custom emojis for *each* starboard

- Leveling, rank, and leaderboard

- Award Roles (XP Roles and Position-base Roles)

- Starboard moderation, such as:

  - Freezing a message, preventing the points from updating on it

  - Forcing a message, so it's on the starboard no matter what

  - Trashing a message, in case a bad message gets on the starboard

- Advanced customization, giving you complete control over the bot

  

If you have any suggestions or found any bugs, please [create an issue](https://github.com/CircuitsBots/Starboard/issues/new/choose).

## Quick Setup

Note: Don't actually type out `< > [ ]` when I give you commands to run. Replace `[p]` with the actual bot prefix which is `sb!` by default. `channel` means type "channel", where as `<channel>` means replace "\<channel\>" with the name of the channel.

**Method 1**

 1. [Invite the bot to your server](https://discord.com/api/oauth2/authorize?client_id=700796664276844612&permissions=388160&scope=bot)
 
 2. Run `[p]setup` and use the setup wizard to create your starboard!
 
 Once completed you can continue to use the setup wizard to modify the settings of the starboard (like emoji being used). A complete list of settings is available in the [wiki](https://github.com/CircuitsBots/Starboard/wiki/Complete-Command-List#starboard).

**Method 2**

1. [Invite the bot to your server](https://discord.com/api/oauth2/authorize?client_id=700796664276844612&permissions=388160&scope=bot)

2. Create a channel for the bot (name it something like #starboard). You can also use a existing channel

3. Type `[p]starboards add <channel>` ("\<channel\>" is the name of the channel you are using)

4. Type `[p]starboards <channel>` to view all the settings for this starboard!

  

The starboard is now good to go, but you might want to change more settings (like the number of reactions needed). A complete list of settings is available in the [wiki](https://github.com/CircuitsBots/Starboard/wiki/Complete-Command-List#starboard).

  

## Self Hosting

These directions are for self-hosting the bot. If you just want a working bot, you can invite the main bot to your server instead.

### What you will need:
- Something to run the bot on
-   A Discord bot application from the [Discord Developer Portal](https://discord.com/developers/applications)
- A Python 3.6 or higher installation
- A PostgreSQL database
### Instructions

- Clone the repo by running `git clone https://github.com/CircuitsBots/Starboard.git` in the command line.

- Make a copy of `bot_config.py.example`, and rename it to `bot_config.py`.

- Update the settings to your liking. If you need help with this, you can join the support server. You only *need* to edit the first two lines, and you can just leave the others the same for now.

- Create a file called `.env`, and inside it paste the contents of the `.env.example` file. The only required fields are `TOKEN`, and `DB_PASSWORD`. If you wish to have statistics for your bot you can fill out `STATCORD_TOKEN` with a token from [Statcord](https://statcord.com)

- If your database is not on the same device as the bot or has a different default user/database you maybe need to edit the bot to account for this. First, head over to the `database/database.py` file. Second, open the file in a text editor and scroll down to line 249 (as of time of writing). Here you will find the connection config. You can edit the database host, dabasase name, and database user to suit your setup.

- Now you need to install the dependencies required for the bot to run. These can be found in the `requirements.txt` file

- Finally run `python bot.py` to run the bot!

  

## Contributing

If you see a bug or possible improvement and want to help out, you can fork this repostory, make the edits, and then create a pull request. Make sure to look at the guidelines in `CONTRIBUTING.md`. I really appreciate any help that you can give.

  

## Bot Lists

[![Discord Bots](https://top.gg/api/widget/700796664276844612.svg)](https://top.gg/bot/700796664276844612)

[![Starboard](https://bots.ondiscord.xyz/bots/700796664276844612/embed?theme=dark&showGuilds=true)](https://bots.ondiscord.xyz/bots/700796664276844612)

[![Bots for Discord](https://botsfordiscord.com/api/bot/700796664276844612/widget)](https://botsfordiscord.com/bots/700796664276844612)

[![Discord Boats](https://discord.boats/api/widget/700796664276844612)](https://discord.boats/bot/700796664276844612)
