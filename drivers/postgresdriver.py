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
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id_0,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid account '{acct_id_0}'")
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id_1,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid account '{acct_id_1}'")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id_0,)
    )
    savings_row = cursor.fetchone()
    if savings_row is None:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id_0}")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_CHECKING} WHERE custid = %s", (acct_id_0,)
    )
    checking_row = cursor.fetchone()
    if checking_row is None:
        raise InvalidAccount(f"No {TABLENAME_CHECKING} for customer #{acct_id_0}")

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

    cursor.execute(
        f"SELECT * FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id,)
    )
    savings_row = cursor.fetchone()
    if savings_row is None:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_CHECKING} WHERE custid = %s", (acct_id,)
    )
    checking_row = cursor.fetchone()
    if checking_row is None:
        raise InvalidAccount(f"No {TABLENAME_CHECKING} for customer #{acct_id}")

    return savings_row[1] + checking_row[1]


def deposit_checking(conn, acct_id: int, amount: float):
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid account '{acct_id}'")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id,)
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal + %s WHERE custid = %s",
        (amount, acct_id),
    )
    conn.commit()


def send_payment(conn, send_acct: int, dest_acct: int, amount: float):
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (send_acct,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid sender account '{send_acct}'")
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (dest_acct,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid destination account '{dest_acct}'")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_CHECKING} WHERE custid = %s", (send_acct,)
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
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid account '{acct_id}'")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id,)
    )
    row = cursor.fetchone()
    if row is None:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

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
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id,),
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"Invalid account name '{acct_id}'")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id,)
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    cursor.execute(
        f"SELECT * FROM {TABLENAME_CHECKING} WHERE custid = %s", (acct_id,)
    )
    if cursor.fetchone() is None:
        raise InvalidAccount(f"No {TABLENAME_CHECKING} for customer #{acct_id}")

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal - %s WHERE custid = %s",
        (amount, acct_id),
    )
    conn.commit()
