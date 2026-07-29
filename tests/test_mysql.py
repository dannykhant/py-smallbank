from __future__ import annotations

import configparser
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql

from drivers.mysqldriver import (
    amalgamate, balance, deposit_checking, send_payment,
    transact_savings, write_check, InvalidAccount, InsufficientFunds,
)

_cfg = configparser.ConfigParser()
_cfg.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mysql.config"))
_mysql = _cfg["mysql"]
DB_CONFIG = dict(
    host=_mysql.get("host", "127.0.0.1"),
    port=_mysql.getint("port", 3306),
    user=_mysql.get("user", "root"),
    password=_mysql.get("password", ""),
    database=_mysql.get("database", "smallbank"),
    autocommit=False,
)


def make_conn():
    conn = pymysql.connect(**DB_CONFIG)
    conn.rollback()
    cur = conn.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("DROP TABLE IF EXISTS CHECKING")
    cur.execute("DROP TABLE IF EXISTS SAVINGS")
    cur.execute("DROP TABLE IF EXISTS ACCOUNTS")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    cur.execute("""
        CREATE TABLE ACCOUNTS (
            custid      BIGINT      NOT NULL,
            name        VARCHAR(64) NOT NULL,
            CONSTRAINT pk_accounts PRIMARY KEY (custid)
        )
    """)
    cur.execute("CREATE INDEX IDX_ACCOUNTS_NAME ON ACCOUNTS (name)")
    cur.execute("""
        CREATE TABLE SAVINGS (
            custid      BIGINT      NOT NULL,
            bal         FLOAT       NOT NULL,
            CONSTRAINT pk_savings PRIMARY KEY (custid),
            FOREIGN KEY (custid) REFERENCES ACCOUNTS (custid)
        )
    """)
    cur.execute("""
        CREATE TABLE CHECKING (
            custid      BIGINT      NOT NULL,
            bal         FLOAT       NOT NULL,
            CONSTRAINT pk_checking PRIMARY KEY (custid),
            FOREIGN KEY (custid) REFERENCES ACCOUNTS (custid)
        )
    """)
    conn.commit()
    return conn


def seed_account(conn, custid, savings_bal, checking_bal, name=None):
    cur = conn.cursor()
    if name is None:
        name = f"{custid:064d}"
    cur.execute("INSERT INTO ACCOUNTS (custid, name) VALUES (%s, %s)", (custid, name))
    cur.execute("INSERT INTO SAVINGS (custid, bal) VALUES (%s, %s)", (custid, savings_bal))
    cur.execute("INSERT INTO CHECKING (custid, bal) VALUES (%s, %s)", (custid, checking_bal))
    conn.commit()


def test_amalgamate():
    conn = make_conn()
    seed_account(conn, 1, 1000.0, 500.0)
    seed_account(conn, 2, 200.0, 300.0)

    amalgamate(conn, 1, 2)

    cur = conn.cursor()
    cur.execute("SELECT bal FROM SAVINGS WHERE custid = 1")
    assert cur.fetchone()[0] == 1000.0

    cur.execute("SELECT bal FROM CHECKING WHERE custid = 1")
    assert cur.fetchone()[0] == 0.0

    cur.execute("SELECT bal FROM SAVINGS WHERE custid = 2")
    bal = cur.fetchone()[0]
    assert bal == 200.0 + (1000.0 + 500.0), f"got {bal}"

    conn.close()
    print("  PASS")


def test_amalgamate_invalid():
    conn = make_conn()
    seed_account(conn, 1, 100.0, 100.0)

    try:
        amalgamate(conn, 1, 999)
        assert False, "expected InvalidAccount"
    except InvalidAccount:
        pass

    conn.close()
    print("  PASS")


def test_balance():
    conn = make_conn()
    seed_account(conn, 5, 2000.0, 3000.0)

    total = balance(conn, 5)
    assert total == 5000.0, f"expected 5000.0, got {total}"

    conn.close()
    print("  PASS")


def test_balance_invalid():
    conn = make_conn()
    try:
        balance(conn, 999)
        assert False, "expected InvalidAccount"
    except InvalidAccount:
        pass
    conn.close()
    print("  PASS")


def test_deposit_checking():
    conn = make_conn()
    seed_account(conn, 10, 0.0, 100.0)

    deposit_checking(conn, 10, 50.0)

    cur = conn.cursor()
    cur.execute("SELECT bal FROM CHECKING WHERE custid = 10")
    assert cur.fetchone()[0] == 150.0

    conn.close()
    print("  PASS")


def test_deposit_checking_invalid():
    conn = make_conn()
    try:
        deposit_checking(conn, 999, 50.0)
        assert False, "expected InvalidAccount"
    except InvalidAccount:
        pass
    conn.close()
    print("  PASS")


def test_send_payment():
    conn = make_conn()
    seed_account(conn, 20, 0.0, 500.0)
    seed_account(conn, 21, 0.0, 100.0)

    send_payment(conn, 20, 21, 200.0)

    cur = conn.cursor()
    cur.execute("SELECT bal FROM CHECKING WHERE custid = 20")
    assert cur.fetchone()[0] == 300.0
    cur.execute("SELECT bal FROM CHECKING WHERE custid = 21")
    assert cur.fetchone()[0] == 300.0

    conn.close()
    print("  PASS")


def test_send_payment_insufficient():
    conn = make_conn()
    seed_account(conn, 22, 0.0, 10.0)
    seed_account(conn, 23, 0.0, 100.0)

    try:
        send_payment(conn, 22, 23, 200.0)
        assert False, "expected InsufficientFunds"
    except InsufficientFunds:
        pass

    conn.close()
    print("  PASS")


def test_transact_savings():
    conn = make_conn()
    seed_account(conn, 30, 500.0, 0.0)

    transact_savings(conn, 30, 100.0)

    cur = conn.cursor()
    cur.execute("SELECT bal FROM SAVINGS WHERE custid = 30")
    assert cur.fetchone()[0] == 400.0

    conn.close()
    print("  PASS")


def test_transact_savings_negative():
    conn = make_conn()
    seed_account(conn, 31, 50.0, 0.0)

    try:
        transact_savings(conn, 31, 100.0)
        assert False, "expected InsufficientFunds"
    except InsufficientFunds:
        pass

    conn.close()
    print("  PASS")


def test_write_check_sufficient():
    conn = make_conn()
    seed_account(conn, 40, 200.0, 300.0)

    write_check(conn, 40, 400.0)

    cur = conn.cursor()
    cur.execute("SELECT bal FROM CHECKING WHERE custid = 40")
    assert cur.fetchone()[0] == -100.0

    conn.close()
    print("  PASS")


def test_write_check_insufficient():
    conn = make_conn()
    seed_account(conn, 41, 50.0, 50.0)

    write_check(conn, 41, 200.0)

    cur = conn.cursor()
    cur.execute("SELECT bal FROM CHECKING WHERE custid = 41")
    assert cur.fetchone()[0] == 50.0 - (200.0 - 1)

    conn.close()
    print("  PASS")


def _setup_tables():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS CHECKING")
    cur.execute("DROP TABLE IF EXISTS SAVINGS")
    cur.execute("DROP TABLE IF EXISTS ACCOUNTS")
    cur.execute("""
        CREATE TABLE ACCOUNTS (custid BIGINT NOT NULL PRIMARY KEY, name VARCHAR(64) NOT NULL)
    """)
    cur.execute("CREATE INDEX IDX_ACCOUNTS_NAME ON ACCOUNTS (name)")
    cur.execute("""
        CREATE TABLE SAVINGS (custid BIGINT NOT NULL PRIMARY KEY, bal FLOAT NOT NULL,
            FOREIGN KEY (custid) REFERENCES ACCOUNTS(custid))
    """)
    cur.execute("""
        CREATE TABLE CHECKING (custid BIGINT NOT NULL PRIMARY KEY, bal FLOAT NOT NULL,
            FOREIGN KEY (custid) REFERENCES ACCOUNTS(custid))
    """)
    conn.commit()
    conn.close()


def _conn_factory():
    return pymysql.connect(**DB_CONFIG)


def test_loader():
    from loader import SmallBankLoader

    _setup_tables()
    loader = SmallBankLoader(
        conn_factory=_conn_factory,
        num_accounts=100,
        scale_factor=1.0,
        load_threads=2,
    )
    loader.load()

    conn = _conn_factory()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ACCOUNTS")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 100, f"expected 100 accounts, got {count}"
    print(f"  loaded {count} accounts")
    print("  PASS")


def test_client_basic():
    from client import SmallBankClient
    from loader import SmallBankLoader

    _setup_tables()
    loader = SmallBankLoader(
        conn_factory=_conn_factory, num_accounts=500, scale_factor=1.0, load_threads=2
    )
    loader.load()

    client = SmallBankClient(
        conn_factory=_conn_factory, num_accounts=500, scale_factor=1.0
    )
    results = client.run(200)
    counts = results["counts"]
    total = sum(counts.values())
    print(f"  executed {total} txns: {counts}")
    assert total == 200, f"expected 200 txns, got {total}"
    print("  PASS")


if __name__ == "__main__":
    tests = [
        ("amalgamate basic", test_amalgamate),
        ("amalgamate invalid", test_amalgamate_invalid),
        ("balance basic", test_balance),
        ("balance invalid", test_balance_invalid),
        ("deposit_checking basic", test_deposit_checking),
        ("deposit_checking invalid", test_deposit_checking_invalid),
        ("send_payment basic", test_send_payment),
        ("send_payment insufficient", test_send_payment_insufficient),
        ("transact_savings basic", test_transact_savings),
        ("transact_savings negative", test_transact_savings_negative),
        ("write_check sufficient", test_write_check_sufficient),
        ("write_check insufficient", test_write_check_insufficient),
    ]

    failed = 0
    for name, fn in tests:
        print(f"  {name}...", end=" ")
        try:
            fn()
        except Exception as e:
            print(f"  FAIL ({e})")
            failed += 1

    if failed:
        print(f"\n{len(tests) - failed}/{len(tests)} passed, {failed} failed")
        import sys
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests passed!")

    print("\n--- Integration tests ---")
    for name, fn in [("loader", test_loader), ("client basic", test_client_basic)]:
        print(f"  {name}...", end=" ")
        try:
            fn()
        except Exception as e:
            print(f"  FAIL ({e})")
            failed += 1

    if failed:
        print(f"\nFAILED: {failed} integration test(s)")
        import sys
        sys.exit(1)
    else:
        print("\nAll integration tests passed!")
