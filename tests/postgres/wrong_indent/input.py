# type: ignore

import datetime
from sqlalchemy import text

key = "ABC"
now = datetime.datetime.now()

sql = f"""
        insert into schema.table
        (
            key,
            datetime,
            updated_time
        )
        values
        (
            '{key}',
            '{now}'
            '{datetime.datetime.now(TZ)}'
        )
        on conflict (key, datetime)
        do nothing
    """
text(sql)
