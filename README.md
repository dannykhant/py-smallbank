# py-smallbank

Python port of the [SmallBank benchmark](https://github.com/apavlo/h-store/tree/master/src/benchmarks/edu/brown/benchmark/smallbank) from H-Store.

A simple OLTP benchmark simulating a bank with accounts, savings, and checking tables, with MySQL as the backend. Loading implementation adapted from [OLTPBench](https://github.com/oltpbenchmark/oltpbench).

## Setup

```bash
uv sync
```

Create the target database in MySQL:
```sql
CREATE DATABASE IF NOT EXISTS `smallbank`;
```

Edit `mysql.config` to match your MySQL instance:
```ini
[mysql]
host = 127.0.0.1
port = 3306
user = root
password = your_password
database = smallbank
```

## CLI Usage

```
uv run python main.py load --reset        # Load 1M accounts (resets tables)
uv run python main.py run                 # Run 10K transactions
uv run python main.py test                # Quick load + benchmark (resets data)
uv run python main.py <command> --help    # Per-command help
```

DB credentials are read from `mysql.config`. CLI flags override config values:

| Option | Source | Default |
|--------|--------|---------|
| `--host` | `mysql.config` | `127.0.0.1` |
| `--port` | `mysql.config` | `3306` |
| `--user` | `mysql.config` | `root` |
| `--password` | `mysql.config` | — |
| `--database` | `mysql.config` | `smallbank` |

### `test`
Quick load + benchmark. Resets data on each run.

| Option | Default |
|--------|---------|
| `--accounts` | `500` |
| `--transactions` | `200` |
| `--threads` | `2` |

### `load`
Bulk-loads account data using `executemany` batching (100K rows per thread).

| Option | Default |
|--------|---------|
| `--accounts` | `1000000` |
| `--scale` | `1.0` |
| `--threads` | auto (num_accounts / 100K) |
| `--reset` | — | Drop and recreate tables before loading |

### `run`
Runs benchmark transactions against existing data.

| Option | Default |
|--------|---------|
| `--accounts` | `1000000` |
| `--scale` | `1.0` |
| `--transactions` | `10000` |

## Running tests

```bash
uv run python tests/test_mysql.py
```

## Project structure

```
py_smallbank/
├── drivers/
│   └── mysqldriver.py    # MySQL transaction procedures
├── tests/
│   └── test_mysql.py     # Test suite (MySQL)
├── main.py               # CLI entry point
├── client.py             # Benchmark client driver
├── loader.py             # Data loader (OLTPBench-style batching)
├── constants.py          # Configuration constants
├── mysql.config          # MySQL connection config
└── schema.sql            # Database schema
```
