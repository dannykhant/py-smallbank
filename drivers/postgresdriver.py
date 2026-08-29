from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import TABLENAME_ACCOUNTS, TABLENAME_SAVINGS, TABLENAME_CHECKING


class InsufficientFunds(Exception):
    pass


class InvalidAccount(Exception):
    pass


def amalgamate(conn, acct_id_0: int, acct_id_1: int):
    cursor = conn.cursor()

    # Validate that every involved account exists (N+1 over account ids).
    for cid in (acct_id_0, acct_id_1):
        cursor.execute(
            f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
            (cid,),
        )
        if cursor.fetchone() is None:
            raise InvalidAccount(f"Invalid account '{cid}'")

    # Fetch the source account's per-table balances (N+1 over tables).
    savings_row = None
    checking_row = None
    for table in (TABLENAME_SAVINGS, TABLENAME_CHECKING):
        cursor.execute(
            f"SELECT * FROM {table} WHERE custid = %s",
            (acct_id_0,),
        )
        row = cursor.fetchone()
        if row is None:
            raise InvalidAccount(f"No {table} for customer #{acct_id_0}")
        if table == TABLENAME_SAVINGS:
            savings_row = row
        else:
            checking_row = row

    total = savings_row[1] + checking_row[1]

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = 0.0 WHERE custid = %s",
        (acct_id_0,),
    )
    cursor.execute(
        f"UPDATE {TABLENAME_SAVINGS} SET bal = bal + %s WHERE custid = %s",
        (total, acct_id_1),
    )
    conn.commit()


def balance(conn, acct_id: int) -> float:
    cursor = conn.cursor()

    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid account '{acct_id}'")

    savings_row = None
    checking_row = None
    for table in (TABLENAME_SAVINGS, TABLENAME_CHECKING):
        cursor.execute(
            f"SELECT * FROM {table} WHERE custid = %s",
            (acct_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise InvalidAccount(f"No {table} for customer #{acct_id}")
        if table == TABLENAME_SAVINGS:
            savings_row = row
        else:
            checking_row = row

    return savings_row[1] + checking_row[1]


def deposit_checking(conn, acct_id: int, amount: float):
    cursor = conn.cursor()

    # Validate account + savings existence (N+1 over tables).
    for table in (TABLENAME_ACCOUNTS, TABLENAME_SAVINGS):
        cursor.execute(
            f"SELECT custid FROM {table} WHERE custid = %s",
            (acct_id,),
        )
        row = cursor.fetchone()
        if row is None:
            if table == TABLENAME_ACCOUNTS:
                raise InvalidAccount(f"Invalid account '{acct_id}'")
            raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal + %s WHERE custid = %s",
        (amount, acct_id),
    )
    conn.commit()


def send_payment(conn, send_acct: int, dest_acct: int, amount: float):
    cursor = conn.cursor()

    # Validate both endpoints exist (N+1 over account ids).
    for cid in (send_acct, dest_acct):
        cursor.execute(
            f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
            (cid,),
        )
        if cursor.fetchone() is None:
            role = "sender" if cid == send_acct else "destination"
            raise InvalidAccount(f"Invalid {role} account '{cid}'")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_CHECKING} WHERE custid = %s",
        (send_acct,),
    )
    row = cursor.fetchone()
    if row is None:
        raise InvalidAccount(
            f"No {TABLENAME_CHECKING} for customer #{send_acct}"
        )

    if row[1] < amount:
        raise InsufficientFunds(
            f"Insufficient {TABLENAME_CHECKING} funds for customer #{send_acct}"
        )

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal - %s WHERE custid = %s",
        (amount, send_acct),
    )
    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal + %s WHERE custid = %s",
        (amount, dest_acct),
    )
    conn.commit()


def transact_savings(conn, acct_id: int, amount: float):
    cursor = conn.cursor()

    # Validate account + savings existence (N+1 over tables).
    for table in (TABLENAME_ACCOUNTS, TABLENAME_SAVINGS):
        cursor.execute(
            f"SELECT custid FROM {table} WHERE custid = %s",
            (acct_id,),
        )
        row = cursor.fetchone()
        if row is None:
            if table == TABLENAME_ACCOUNTS:
                raise InvalidAccount(f"Invalid account '{acct_id}'")
            raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_SAVINGS} WHERE custid = %s",
        (acct_id,),
    )
    row = cursor.fetchone()
    if row[1] - amount < 0:
        raise InsufficientFunds(
            f"Negative {TABLENAME_SAVINGS} balance for customer #{acct_id}"
        )

    cursor.execute(
        f"UPDATE {TABLENAME_SAVINGS} SET bal = bal - %s WHERE custid = %s",
        (amount, acct_id),
    )
    conn.commit()


def write_check(conn, acct_id: int, amount: float):
    cursor = conn.cursor()

    # Validate account + savings + checking existence (N+1 over tables).
    for table in (TABLENAME_ACCOUNTS, TABLENAME_SAVINGS, TABLENAME_CHECKING):
        cursor.execute(
            f"SELECT custid FROM {table} WHERE custid = %s",
            (acct_id,),
        )
        row = cursor.fetchone()
        if row is None:
            if table == TABLENAME_ACCOUNTS:
                raise InvalidAccount(f"Invalid account name '{acct_id}'")
            raise InvalidAccount(f"No {table} for customer #{acct_id}")

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal - %s WHERE custid = %s",
        (amount, acct_id),
    )
    conn.commit()
