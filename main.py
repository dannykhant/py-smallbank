from __future__ import annotations

import argparse
import configparser
import datetime
import os
import sys
import time

import pymysql

from loader import SmallBankLoader
from client import SmallBankClient

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mysql.config")


def _load_config(path: str = CONFIG_PATH) -> dict:
    cfg = configparser.ConfigParser()
    cfg.read(path)
    section = cfg["mysql"]
    return {
        "host": section.get("host", "127.0.0.1"),
        "port": section.getint("port", 3306),
        "user": section.get("user", "root"),
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


def _conn_factory(host, port, user, password, database):
    def factory():
        return pymysql.connect(
            host=host, port=port, user=user,
            password=password, database=database,
            autocommit=False,
        )
    return factory


def _format_table(results: dict, duration: float):
    lines = []
    lines.append("")
    lines.append(f"Execution Results after {duration:.0f} seconds")
    lines.append("--------------------------------------------------------------------------------")
    lines.append(f"  {'':16s} {'Executed':>12s} {'Time (µs)':>20s} {'Rate':>20s}")

    total_count = 0
    total_usec = 0.0

    for name in sorted(results):
        c = results[name]["count"]
        t = results[name]["latency"]
        total_count += c
        total_usec += t
        usec = t * 1_000_000
        rate = c / t if t > 0 else 0.0
        lines.append(
            f"  {name:16s} {c:>12d} {usec:>20.0f} {rate:>20.0f} txn/s"
        )

    lines.append("--------------------------------------------------------------------------------")
    total_usec_total = total_usec * 1_000_000
    total_rate = total_count / total_usec if total_usec > 0 else 0.0
    lines.append(
        f"  {'TOTAL':16s} {total_count:>12d} {total_usec_total:>20.0f} {total_rate:>20.0f} txn/s"
    )
    return "\n".join(lines)


def cmd_load(args):
    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user,
        password=args.password, database=args.database,
    )
    _init_schema(conn, reset=args.reset)
    conn.close()

    conn_factory = _conn_factory(
        args.host, args.port, args.user, args.password, args.database
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


def cmd_run(args):
    conn_factory = _conn_factory(
        args.host, args.port, args.user, args.password, args.database
    )
    client = SmallBankClient(
        conn_factory=conn_factory,
        num_accounts=args.accounts,
        scale_factor=args.scale,
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


def cmd_test(args):
    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user,
        password=args.password, database=args.database,
    )
    _init_schema(conn, reset=True)
    conn.close()

    conn_factory = _conn_factory(
        args.host, args.port, args.user, args.password, args.database
    )

    loader = SmallBankLoader(
        conn_factory=conn_factory,
        num_accounts=args.accounts,
        scale_factor=1.0,
        load_threads=args.threads,
    )
    _log(
        f"Loading {args.accounts} accounts ({args.threads} threads)...",
        "loadStart",
    )
    load_start = time.time()
    loader.load()
    load_elapsed = time.time() - load_start
    _log(f"Data loading complete ({load_elapsed:.0f}s)", "loadFinish")

    client = SmallBankClient(
        conn_factory=conn_factory,
        num_accounts=args.accounts,
        scale_factor=1.0,
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


def main():
    config = _load_config()

    parser = argparse.ArgumentParser(
        prog="py-smallbank",
        description="SmallBank OLTP Benchmark",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_db_args(p):
        p.add_argument("--host", default=config["host"])
        p.add_argument("--port", type=int, default=config["port"])
        p.add_argument("--user", default=config["user"])
        p.add_argument("--password", default=config["password"])
        p.add_argument("--database", default=config["database"])

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
    p_run.set_defaults(func=cmd_run)

    p_test = sub.add_parser("test", help="Quick load + benchmark (resets data)")
    add_db_args(p_test)
    p_test.add_argument("--accounts", type=int, default=500)
    p_test.add_argument("--transactions", type=int, default=200)
    p_test.add_argument("--threads", type=int, default=2)
    p_test.set_defaults(func=cmd_test)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
