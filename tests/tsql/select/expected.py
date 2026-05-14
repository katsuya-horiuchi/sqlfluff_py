table_name = "my_table"
sql = """
    select
        a,
        b,
        [field]
    from
        [my_schema].[{table_name}]
"""
