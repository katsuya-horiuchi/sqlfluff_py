# sqlfluff_py

SQLFluff for python script


> [!WARNING]
> This project is in alpha stage.
> Using the tool may cause unreversable changes in python code.


## Installation

```python
$ pip install sqlfluff_py
```

## Usage

You can use CLI tool from terminal.

When using the tool, you must specify the following:
* `-i` for input file
* `-d` for dialect (See sqlfluff's documentation for available dialects)
* `-p` for regex pattern to identify variables for query


```bash
$ sqlfluff_py -i your_script.py -d ansi -p query
```

Optionally you can specify `-o` for output file, in case you would like to
keep the original file.
By default the input file will be overwritten.

```bash
$ sqlfluff_py -i your_script.py -d ansi -p query -o fixed_script.py
```


## TODO

* Handle tokens' position properly
* Read configuration from `pyproject.toml`
* Make yaml for pre-commit
