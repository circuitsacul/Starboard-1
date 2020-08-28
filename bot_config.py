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