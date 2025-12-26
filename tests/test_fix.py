import pathlib
import re

from sqlfluff_py.fix import get_script

directory = pathlib.Path(__file__).parent

script_1 = directory.joinpath("script_1.py")
script_2 = directory.joinpath("script_2.py")


def test_get_script():
    with open(script_1, 'r', encoding='utf-8') as fp:
        result = get_script(fp.read(), re.compile(r"sql_"), "ansi")
    print(result)
    assert result == open(script_2, "r", encoding="utf-8").read()
