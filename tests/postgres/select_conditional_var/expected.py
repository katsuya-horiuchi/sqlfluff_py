# type: ignore

import datetime
from sqlalchemy import text

var = "foo"
var_sql = f"'{var}'" if var is not None else "null"
sql = f"""
    insert into some_schema.some_table
    (key, f1, f2, f3)
    values
    (
        'AA',
        {var_sql},
        'B',
        '{datetime.datetime.now()}'
    )
    on conflict (ticker)
    do update set
        f1 = 'AA',
        f2 = {var_sql},
        updated_time = '{datetime.datetime.now()}'
"""
text(sql)
