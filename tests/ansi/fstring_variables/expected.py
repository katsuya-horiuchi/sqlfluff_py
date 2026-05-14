# type: ignore


def func():
    table_name = "my_table"
    sql = f"""
        select
            a,
            b,
            c
        from
            dbo.{table_name}
    """
    return sql
