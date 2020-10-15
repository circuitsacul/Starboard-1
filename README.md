## About Starboard
Starboard is an advanced, reliable, and highly customizable starboard bot. I've been working on this project for a while now, mostly for use in personal servers. When it turned out better than I imagined, I open-sourced it and posted it to bot lists. I hope you find this code and/or bot useful. This documentation gives you a quick start to using the bot. If you see a problem, please let me know. You can use the bots `suggest` command, or you can join the support server. My discord username is `@Circuit#5585`.

## Useful Links
[Click here for a demonstration](https://drive.google.com/file/d/1hIeeL8Y_PweQIovyAzsXJX4_-gZiqstU/view?usp=sharing)

[Invite Starboard to your server](https://discord.com/api/oauth2/authorize?client_id=700796664276844612&permissions=388160&scope=bot)

[Join the support server](https://discord.gg/3gK8mSA)

[Starboard Documentation/Wiki](https://github.com/CircuitsBots/Starboard/wiki)

## Starboard's Features
 - Supports multiple starboards
 - Supports multiple normal and custom emojis for *each* starboard
 - Leveling, rank, and leaderboard
 - Starboard moderation, such as:
   - Freezing a message, preventing the points from updating on it
   - Forcing a message, so it's on the starboard no matter what
   - Trashing a message, in case a bad message gets on the starboard
 - Advanced customization, giving you complete control over the bot

If you have any suggestions or found any bugs, please [create an issue](https://github.com/CircuitsBots/Starboard/issues/new/choose).
 
## Quick Setup
Note: Don't actually type out `< > [ ]` when I give you commands to run. Replace `[p]` with the actual bot prefix. `channel` means type "channel", where as `<channel>` means replace "\<channel\>" with the name of the channel.
 1. [Invite the bot to your server](https://discord.com/api/oauth2/authorize?client_id=700796664276844612&permissions=388160&scope=bot)
 2. Create a channel for the bot (name it something like #starboard).
 3. Type `[p]add <channel>` ("\<channel\>" is the name of the channel you just created)
 4. Type `[p]addEmoji <channel> <emoji>` (`<emoji>` is usually ":star:")

The starboard is now good to go, but you might want to change more settings (like the number of reactions needed). A complete list of setting in the [wiki](https://github.com/CircuitsBots/Starboard/wiki).

## Self Hosting
These directions are for self-hosting the bot. If you just want a working bot, you can invite it to your server instead.
 - Clone the repo by running `git clone https://github.com/CircuitsBots/Starboard.git` in the command line.
 - Make a copy of `bot_config.py.example`, and rename it to `bot_config.py`. 
   - Update the settings to your liking. If you need help with this, you can join the support server.
 - Create a file called `.env`, and inside it put `TOKEN="your token"`
 - Run `python bot.py` to run the bot!

## Contributing
If you see a bug or possible improvement and want to help out, you can fork this repostory, make the edits, and then create a pull request. Make sure to look at the guidelines in `CONTRIBUTING.md`. I really appreciate any help that you can give.

## Bot Lists
[![Starboard](https://bots.ondiscord.xyz/bots/700796664276844612/embed?theme=dark&showGuilds=true)](https://bots.ondiscord.xyz/bots/700796664276844612)
[![Bots for Discord](https://botsfordiscord.com/api/bot/700796664276844612/widget)](https://botsfordiscord.com/bots/700796664276844612)
