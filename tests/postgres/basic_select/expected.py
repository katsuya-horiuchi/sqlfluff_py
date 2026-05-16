# type: ignore

import datetime
from sqlalchemy import text

key = "ABC"

sql = f"""
    select
        key,
        datetime,
        updated_time
    from
        schema.table
    where
        key = '{key}'
"""
text(sql)
