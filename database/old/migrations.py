async def migrate(db):
    add1 = \
        """ALTER TABLE members
        ADD given int DEFAULT 0;"""
    add2 = \
        """ALTER TABLE members
        ADD received int DEFAULT 0;"""
    add3 = \
        """ALTER TABLE members
        ADD on_sb int DEFAULT 0;"""

    add4 = \
        """ALTER TABLE members
        ADD on_lb bool DEFAULT 0;"""

    add5 = \
        """ALTER TABLE members
        ADD xp int NOT NULL DEFAULT 0"""
    add6 = \
        """ALTER TABLE members
        ADD lvl int NOT NULL DEFAULT 0"""


    conn = await db.connect()
    c = await conn.cursor()
    async with db.lock:
        try:
            await c.execute(add1)
            await c.execute(add2)
            #await c.execute(add3)
        except:
            pass
        try:
            await c.execute(add4)
        except:
            pass
        try:
            await c.execute(add5)
            await c.execute(add6)
        except:
            pass

        await conn.commit()
        await conn.close()