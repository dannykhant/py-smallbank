# py-smallbank

Python port of the [SmallBank benchmark](https://github.com/apavlo/h-store/tree/master/src/benchmarks/edu/brown/benchmark/smallbank) from H-Store.

A simple OLTP benchmark simulating a bank with accounts, savings, and checking tables, with MySQL or PostgreSQL as the backend. Loading implementation adapted from [OLTPBench](https://github.com/oltpbenchmark/oltpbench).

## Setup

```bash
uv sync
```

### MySQL

Create the target database in MySQL:
```sql
CREATE DATABASE IF NOT EXISTS `smallbank`;
```

### PostgreSQL

Create the target database in PostgreSQL:
```sql
CREATE DATABASE smallbank;
```

DB credentials for both drivers live in a single `db.config` file (see
`db.config-example`), one `[ini]` section per driver:
```ini
[mysql]
host = 127.0.0.1
port = 3306
user = root
password = your_password
database = smallbank

[postgres]
host = 127.0.0.1
port = 5432
user = postgres
password = your_password
database = smallbank
```

## CLI Usage

```
uv run python main.py load --driver postgres --reset   # Load accounts (resets tables); --accounts sets how many
uv run python main.py run  --driver postgres           # Run 10K transactions against LOADED data (note: --accounts must match the load)
uv run python main.py test --driver postgres           # Quick load + benchmark in one step (resets data)
uv run python main.py <command> --help                 # Per-command help
```

Note: `run` does not load data. Load first with `load` (or use `test`, which
loads and benchmarks together), and make sure `run`'s `--accounts` matches the
number of accounts you loaded.

By default the `--driver` is `mysql`. DB credentials are read from `db.config`,
from the section matching the selected driver. CLI flags override config values:

| Option | Source | Default (mysql) | Default (postgres) |
|--------|--------|-----------------|--------------------|
| `--driver` | CLI | `mysql` | — |
| `--host` | `db.config` | `127.0.0.1` | `127.0.0.1` |
| `--port` | `db.config` | `3306` | `5432` |
| `--user` | `db.config` | `root` | `postgres` |
| `--password` | `db.config` | — | — |
| `--database` | `db.config` | `smallbank` | `smallbank` |

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
Runs benchmark transactions against **existing** data. You must load the
database first (see `load`) — `run` does not create any accounts.

**Important:** `--accounts` must match the number of accounts you loaded.
`run` generates random account IDs in `[hotspot_size, num_accounts)` and
expects every one of them to already exist in the DB; if the loaded data
covers a smaller range, almost every transaction will fail with `InvalidAccount`
and be counted as `ERROR`.

Typical workflow:
```bash
uv run python main.py load --driver postgres --accounts 1000
uv run python main.py run  --driver postgres --accounts 1000 --transactions 10000
```

| Option | Default |
|--------|---------|
| `--accounts` | `1000000` |
| `--scale` | `1.0` |
| `--transactions` | `10000` |

## Running tests

```bash
uv run python tests/test_mysql.py       # MySQL test suite
uv run python tests/test_postgres.py    # PostgreSQL test suite
```

## Project structure

```
py_smallbank/
├── drivers/
│   ├── mysqldriver.py     # MySQL transaction procedures
│   └── postgresdriver.py  # PostgreSQL transaction procedures
├── tests/
│   ├── test_mysql.py      # Test suite (MySQL)
│   └── test_postgres.py   # Test suite (PostgreSQL)
├── main.py               # CLI entry point
├── client.py             # Benchmark client driver
├── loader.py             # Data loader (OLTPBench-style batching)
├── constants.py          # Configuration constants
├── db.config             # Combined connection config (MySQL + PostgreSQL)
└── schema.sql            # Database schema
```
