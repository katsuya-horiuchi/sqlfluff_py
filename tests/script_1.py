# type: ignore

def func():
    sql = """
        select
            a,
            b, c
        from [dbo].[table_name]
    """
    return sql


schema = "dbo"
table_name = "bar"

# Python variables inside query
sql_2 = f"""
    select
        a, b, c
    from
        {schema}.{table_name}
"""

# Python variables, inside bracket
sql_3 = """
    select
        a, b, c
    from
        [{schema}].[{table_name}]
"""
