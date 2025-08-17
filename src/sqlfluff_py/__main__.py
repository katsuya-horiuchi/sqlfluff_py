import argparse
import logging
import re

from sqlfluff_py import get_script


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--input-file", required=True, help="Path to input file"
    )
    parser.add_argument(
        "-p",
        "--pattern",
        required=True,
        help="Regex pattern that identifies variables of SQL query",
    )
    parser.add_argument(
        "-d",
        "--dialect",
        type=str,
        required=True,
        help="Dialect passed to sqlfluff",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        help=(
            "(Optional) Path to output file. "
            "By default file specified with -i flag will be overwritten. "
            "Using this flag will allow you to create a new file instead."
        ),
    )
    parser.add_argument(
        "-l",
        "--logging-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.logging_level))
    # Disable logging for sqlfluff
    logging.getLogger("sqlfluff").setLevel(logging.ERROR)

    with open(args.input_file, encoding="utf-8") as fp:
        script = fp.read()

    output_file = (
        args.output_file if args.output_file is not None else args.input_file
    )

    output = get_script(script, re.compile(rf"{args.pattern}"), args.dialect)
    if script == output:
        logging.info(
            f"No change was made after running sqlfluff: {args.input_file}"
        )
        return 0

    with open(output_file, "w", encoding="utf-8") as fp:
        fp.write(output)

    logging.info(f"File was formatted: `{args.input_file}`.")
    if args.output_file:
        logging.info(f"New file was created: `{output_file}`")
    return 0
