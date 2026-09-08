from __future__ import annotations

import argparse
import configparser
import datetime
import importlib
import os
import sys
import time

from loader import SmallBankLoader
from client import SmallBankClient
from constants import (
    HOTSPOT_PERCENTAGE,
    HOTSPOT_USE_FIXED_SIZE,
    HOTSPOT_FIXED_SIZE,
)

DRIVERS = {
    "mysql": "mysql",
    "postgres": "postgres",
}

CONFIG_FILENAME = "db.config"


def _load_config(driver: str) -> dict:
    config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        CONFIG_FILENAME,
    )
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    section = cfg[driver]
    return {
        "host": section.get("host", "127.0.0.1"),
        "port": section.getint("port", 5432 if driver == "postgres" else 3306),
        "user": section.get("user", "postgres" if driver == "postgres" else "root"),
        "password": section.get("password", ""),
        "database": section.get("database", "smallbank"),
    }


def _log(message: str, tag: str = "main"):
    ts = datetime.datetime.now().strftime("%m-%d-%Y %H:%M:%S")
    print(f"{ts} [{tag}] INFO : {message}")


def _init_schema(conn, reset: bool = False):
    cur = conn.cursor()
    if reset:
        cur.execute("DROP TABLE IF EXISTS CHECKING")
        cur.execute("DROP TABLE IF EXISTS SAVINGS")
        cur.execute("DROP TABLE IF EXISTS ACCOUNTS")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ACCOUNTS (
            custid      BIGINT      NOT NULL,
            name        VARCHAR(64) NOT NULL,
            CONSTRAINT pk_accounts PRIMARY KEY (custid)
        )
    """)
    cur.execute("CREATE INDEX IDX_ACCOUNTS_NAME ON ACCOUNTS (name)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS SAVINGS (
            custid      BIGINT      NOT NULL,
            bal         FLOAT       NOT NULL,
            CONSTRAINT pk_savings PRIMARY KEY (custid),
            FOREIGN KEY (custid) REFERENCES ACCOUNTS (custid)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS CHECKING (
            custid      BIGINT      NOT NULL,
            bal         FLOAT       NOT NULL,
            CONSTRAINT pk_checking PRIMARY KEY (custid),
            FOREIGN KEY (custid) REFERENCES ACCOUNTS (custid)
        )
    """)
    conn.commit()


def _ensure_database(driver: str, host, port, user, password, database):
    if driver == "postgres":
        import psycopg2
        admin = psycopg2.connect(
            host=host, port=port, user=user,
            password=password, dbname="postgres",
        )
        admin.autocommit = True
        cur = admin.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
        if not cur.fetchone():
            cur.execute('CREATE DATABASE "%s"' % database.replace('"', '""'))
        cur.close()
        admin.close()
    else:
        import pymysql
        admin = pymysql.connect(
            host=host, port=port, user=user,
            password=password,
        )
        admin.autocommit = True
        cur = admin.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS `%s`" % database)
        cur.close()
        admin.close()


def _connect(driver: str, host, port, user, password, database):
    if driver == "postgres":
        import psycopg2
        return psycopg2.connect(
            host=host, port=port, user=user,
            password=password, dbname=database,
        )
    import pymysql
    return pymysql.connect(
        host=host, port=port, user=user,
        password=password, database=database,
        autocommit=False,
    )


def _conn_factory(driver: str, host, port, user, password, database):
    def factory():
        return _connect(driver, host, port, user, password, database)
    return factory


def _format_table(results: dict, duration: float):
    lines = []
    lines.append("")
    lines.append(f"Execution Results after {duration:.2f} seconds")
    lines.append("--------------------------------------------------------------------------------")
    lines.append(f"  {'':16s} {'Executed':>12s} {'Time (ms)':>20s} {'Rate':>20s}")

    total_count = 0
    total_time = 0.0
    error_entries = []

    for name in sorted(results):
        c = results[name]["count"]
        t = results[name]["latency"]
        if name == "ERROR":
            error_entries.append((name, c, t))
            continue
        if name == "TOTAL":
            continue
        total_count += c
        total_time += t
        ms = t * 1_000
        rate = c / t if t > 0 else 0.0
        lines.append(
            f"  {name:16s} {c:>12d} {ms:>20.5f} {rate:>20.5f} txn/s"
        )

    lines.append("--------------------------------------------------------------------------------")
    total_ms = total_time * 1_000
    total_rate = total_count / total_time if total_time > 0 else 0.0
    lines.append(
        f"  {'TOTAL':16s} {total_count:>12d} {total_ms:>20.5f} {total_rate:>20.5f} txn/s"
    )

    for name, c, t in error_entries:
        lines.append(
            f"  {name:16s} {c:>12d} {'-':>20s} {'-':>20s}"
        )
    return "\n".join(lines)


def _format_dat(results: dict, duration: float = 0.0) -> str:
    lines = ["transaction,executed,execution_time,transaction_rate"]
    total_count = 0
    total_time = 0.0

    for name in sorted(results):
        if name in ("ERROR", "TOTAL"):
            continue
        c = results[name]["count"]
        t = results[name]["latency"]
        total_count += c
        total_time += t
        ms = t * 1_000
        rate = c / t if t > 0 else 0.0
        lines.append(f"{name},{c},{ms:.5f},{rate:.5f}")

    total_ms = total_time * 1_000
    total_rate = total_count / total_time if total_time > 0 else 0.0
    lines.append(f"TOTAL,{total_count},{total_ms:.5f},{total_rate:.5f}")

    return "\n".join(lines) + "\n"


def _write_output(path: str, results: dict, duration: float = 0.0):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    content = _format_dat(results, duration)
    with open(path, "w") as f:
        f.write(content)
    _log(f"Results written to {path}", "output")


def _resolve_db(args) -> dict:
    cfg = _load_config(args.driver)
    return {
        "driver": args.driver,
        "host": args.host if args.host is not None else cfg["host"],
        "port": args.port if args.port is not None else cfg["port"],
        "user": args.user if args.user is not None else cfg["user"],
        "password": args.password if args.password is not None else cfg["password"],
        "database": args.database if args.database is not None else cfg["database"],
    }


def _make_client(db, **kwargs):
    driver_mod = importlib.import_module(f"drivers.{db['driver']}driver")
    conn_factory = _conn_factory(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )
    return SmallBankClient(conn_factory=conn_factory, driver=driver_mod, **kwargs)


def cmd_load(args):
    db = _resolve_db(args)
    _ensure_database(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )
    conn = _connect(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )
    _init_schema(conn, reset=args.reset)
    conn.close()

    conn_factory = _conn_factory(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )
    loader = SmallBankLoader(
        conn_factory=conn_factory,
        num_accounts=args.accounts,
        scale_factor=args.scale,
        load_threads=args.threads,
    )
    _log(
        f"Loading {loader.num_accounts} accounts ({args.threads} threads)...",
        "loadStart",
    )
    start = time.time()
    loader.load()
    elapsed = time.time() - start
    _log(f"Data loading complete ({elapsed:.0f}s)", "loadFinish")


def _warn_undersized(args):
    scale = getattr(args, "scale", 1.0)
    num_accounts = int(round(args.accounts * scale))
    if HOTSPOT_USE_FIXED_SIZE:
        hotspot_size = HOTSPOT_FIXED_SIZE
    else:
        hotspot_size = int((HOTSPOT_PERCENTAGE / 100.0) * num_accounts)
    hot_accounts = num_accounts - hotspot_size
    if hot_accounts <= 0:
        _log(
            "Loaded account count is <= the hotspot size; all "
            "transactions target the same few accounts.",
            "warn",
        )
        return
    reuse = args.transactions / hot_accounts
    if args.transactions > hot_accounts:
        _log(
            f"num_accounts ({num_accounts}) is much smaller than the "
            f"transaction count ({args.transactions}). Hot accounts "
            f"~{hot_accounts} will be reused ~{reuse:.1f}x per run, which "
            f"drains checking balances and inflates InsufficientFunds "
            f"aborts (especially SEND_PAYMENT). Use many more accounts "
            f"than transactions for a realistic benchmark.",
            "warn",
        )


def cmd_run(args):
    db = _resolve_db(args)
    _warn_undersized(args)
    client = _make_client(
        db, num_accounts=args.accounts, scale_factor=args.scale
    )
    _log(
        f"Executing benchmark for {args.transactions} transactions",
        "execute",
    )
    start = time.time()
    results = client.run(args.transactions)
    elapsed = time.time() - start

    counts = results["counts"]
    latencies = results["latencies"]

    combined = {}
    for name in set(list(counts.keys()) + list(latencies.keys())):
        combined[name] = {
            "count": counts.get(name, 0),
            "latency": latencies.get(name, 0.0),
        }

    print(_format_table(combined, elapsed))
    if getattr(args, "output_path", None):
        _write_output(args.output_path, combined, elapsed)


def cmd_test(args):
    db = _resolve_db(args)
    _ensure_database(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )
    conn = _connect(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )
    _init_schema(conn, reset=True)
    conn.close()

    conn_factory = _conn_factory(
        db["driver"], db["host"], db["port"], db["user"],
        db["password"], db["database"],
    )

    loader = SmallBankLoader(
        conn_factory=conn_factory,
        num_accounts=args.accounts,
        scale_factor=1.0,
        load_threads=args.threads,
    )
    _warn_undersized(args)
    _log(
        f"Loading {args.accounts} accounts ({args.threads} threads)...",
        "loadStart",
    )
    load_start = time.time()
    loader.load()
    load_elapsed = time.time() - load_start
    _log(f"Data loading complete ({load_elapsed:.0f}s)", "loadFinish")

    client = _make_client(db, num_accounts=args.accounts, scale_factor=1.0)
    _log(
        f"Executing benchmark for {args.transactions} transactions",
        "execute",
    )
    start = time.time()
    results = client.run(args.transactions)
    elapsed = time.time() - start

    counts = results["counts"]
    latencies = results["latencies"]

    combined = {}
    for name in set(list(counts.keys()) + list(latencies.keys())):
        combined[name] = {
            "count": counts.get(name, 0),
            "latency": latencies.get(name, 0.0),
        }

    print(_format_table(combined, elapsed))
    if getattr(args, "output_path", None):
        _write_output(args.output_path, combined, elapsed)


def main():
    parser = argparse.ArgumentParser(
        prog="py-smallbank",
        description="SmallBank OLTP Benchmark",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_db_args(p):
        p.add_argument("--driver", choices=list(DRIVERS), default="mysql")
        p.add_argument("--host", default=None)
        p.add_argument("--port", type=int, default=None)
        p.add_argument("--user", default=None)
        p.add_argument("--password", default=None)
        p.add_argument("--database", default=None)

    p_load = sub.add_parser("load", help="Load initial data")
    add_db_args(p_load)
    p_load.add_argument("--accounts", type=int, default=1000000)
    p_load.add_argument("--scale", type=float, default=1.0)
    p_load.add_argument("--threads", type=int, default=4)
    p_load.add_argument("--reset", action="store_true", help="Drop and recreate tables before loading")
    p_load.set_defaults(func=cmd_load)

    p_run = sub.add_parser("run", help="Run benchmark transactions")
    add_db_args(p_run)
    p_run.add_argument("--accounts", type=int, default=1000000)
    p_run.add_argument("--scale", type=float, default=1.0)
    p_run.add_argument("--transactions", type=int, default=10000)
    p_run.add_argument("--output-path", default=None, help="Path to save benchmark results in .dat format")
    p_run.set_defaults(func=cmd_run)

    p_test = sub.add_parser("test", help="Quick load + benchmark (resets data)")
    add_db_args(p_test)
    p_test.add_argument("--accounts", type=int, default=500)
    p_test.add_argument("--transactions", type=int, default=200)
    p_test.add_argument("--threads", type=int, default=2)
    p_test.add_argument("--output-path", default=None, help="Path to save benchmark results in .dat format")
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
