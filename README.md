# Starboard

Starboard is an advanced, reliable, and highly-customizable starboard bot. This documentation gives you a quick start to using the bot. If you see a problem, please let me know. You can use the bots `suggest` command, or you can join the support server. My discord username is `@Circuit#5585`.

[Click here for a demonstration](https://drive.google.com/file/d/1hIeeL8Y_PweQIovyAzsXJX4_-gZiqstU/view?usp=sharing)

[Invite Starboard to your server](https://discord.com/api/oauth2/authorize?client_id=700796664276844612&permissions=388160&scope=bot)

[Join the support server](https://discord.gg/3gK8mSA)

## Bot Features:
 - Supports multiple starboards
 - Supports multiple normal and custom emojis for *each* starboard
 - Starboard moderation, such as:
   - Freezing a message, preventing the points from updating on it
   - Forcing a message, so it's on the starboard no matter what
   - Trashing a message, in case a bad message gets on the starboard
 - Advanced customization, giving you complete control over the bot
 
 I'm planning on putting more info in the [wiki](https://github.com/CircuitsBots/Starboard/wiki)
 
## Quick Setup:
Note: Don't actually type out `< > [ ]` when I give you commands to run. `channel` means type "channel", where as `<channel>` means replace "\<channel\>" with the name of the channel.
 1. [Invite the bot to your server](https://discord.com/api/oauth2/authorize?client_id=700796664276844612&permissions=388160&scope=bot)
 2. Create a channel for the bot (name it something like #starboard).
 3. Type `sb!add <channel>` ("\<channel\>" is the name of the channel you just created)
 4. Type `sb!addEmoji <channel> <emoji>` (`<emoji>` is usually ":star:")

The starboard is now good to go, but you might want to change more settings (like the number of reactions needed). A complete list of setting in the [wiki](https://github.com/CircuitsBots/Starboard/wiki).

## Self Hosting:
These directions are for self-hosting the bot. If you just want a working bot, you can invite it to your server instead.
 - Make a copy of `bot_config.py.example`, and rename it to `bot_config.py`. 
   - Update the settings to your liking. If you need help with this, you can join the support server.
 - Create a file called `.env`, and inside it put `TOKEN="your token"`
 - Run `python bot.py` to run the bot!
