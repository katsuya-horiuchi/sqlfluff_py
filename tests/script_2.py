import textwrap


schema = "dbo"
table_name = "bar"

sql_2 = textwrap.dedent(
    f"""select
        a, b, c
        from
    {schema}.{table_name}
   """
)
