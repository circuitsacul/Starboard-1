DB_PATH = "database/sql/database.db" # str
BETA_DB_PATH = "database/sql/beta_database.db" # str

INVITE = "https://discord.com/api/oauth2/authorize?client_id=745642023964639333&permissions=379968&scope=bot" # str
SUPPORT_SERVER = "https://discord.gg/3gK8mSA" # str
SOURCE_CODE = "https://github.com/CircuitSacul/Starboard" # str or None
DONATE = "https://donatebot.io/checkout/725336160112738385" # str or None

SUPPORT_SERVER_ID = 725336160112738385 # int

COLOR = 0xfffb00 # hex
MISTAKE_COLOR = 0xffaa00 # hex
ERROR_COLOR = 0xff0000 # hex

PATRON_LEVELS = {
    "1diL2G7PbA": {
        'display': {
            'title': 'Patron',
            'description': """For all servers you own:\
                \n**- Up to 3 starboards**\
                \n**- Up to 3 emojis per starboard**"""
        },
        'gives_role': 748250027264180294,
        'num': 1 # The level... Essentially means that level 2 will have all the features level 1 has. Can all be set to 0 if needed
    },
    "bJZn0tdzNl": {
        'display': {
            'title': 'Gold Patron',
            'description': """For all servers you own:\
                \n**- Up to 5 starboards**\
                \n**- Up to 5 emojis per starboard**"""
        },
        'gives_role': 748348092566208542,
        'num': 2
    },
    "wC2NCNJmPF": {
        'display': {
            'title': 'Diamond Patron',
            'description': """For all servers you own:\
                \n**- Unlimited starboards**\
                \n**- Unlimited emojis per starboard**"""
        },
        'gives_role': 748250231434510366,
        'num': 3
    }
}

# Markdown, str
PRIVACY_POLICY = \
"""**__Privacy Policy for Starboard__**
This is just information on what data we store, why we store it, and how we handle it.

We only ever store information if it is needed to provide proper functionality.
We do not peek or analyze this information -- it use purely to perform its job. The only exception would be if you gave permission.

The following is a list of the information we store, when we store it, and why.

**User Ids**
Stored when a user reacts to a message, to prevent "double starring" as well as to keep track of the leaderboard
Stored when a user's message is reacted to, to track leaderboard as well as to prevent "self starring"
Stored when a user calls a command, to keep track of who is a bot and who is a normal user

**Message Ids**
Stored when a message receives a reaction, to keep track of the number of reactions it has

**Reactions/Emojis**
If the emoji is custom, we store it's id, otherwise we simply store the emoji

Stored to keep track of which emojis are "starboard emojis", allowing us to count points on a message

**Channel Ids**
Stored if you set a channel as a starboard, to keep track of what channels are starboards
Stored if a message in this channel is sent, to keep track of where to find that message later

There are a few other things, such as if a channel is nsfw or not.
If you have any questions or want more info, you can type `sb!links` to get a link to the support server
"""