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
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid account '{acct_id_0}'")
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id_1,),
    )
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid account '{acct_id_1}'")

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id_0,)
    )
    row = cursor.fetchone()
    if not row:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id_0}")
    savings_bal = row[0]

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_CHECKING} WHERE custid = %s", (acct_id_0,)
    )
    row = cursor.fetchone()
    if not row:
        raise InvalidAccount(f"No {TABLENAME_CHECKING} for customer #{acct_id_0}")
    checking_bal = row[0]

    total = savings_bal + checking_bal

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
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid account '{acct_id}'")

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_SAVINGS} WHERE custid = %s", (acct_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")
    savings_bal = row[0]

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_CHECKING} WHERE custid = %s", (acct_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise InvalidAccount(f"No {TABLENAME_CHECKING} for customer #{acct_id}")
    checking_bal = row[0]

    total = savings_bal + checking_bal
    return total


def deposit_checking(conn, acct_id: int, amount: float):
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (acct_id,),
    )
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid account '{acct_id}'")

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
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid sender account '{send_acct}'")

    cursor.execute(
        f"SELECT custid FROM {TABLENAME_ACCOUNTS} WHERE custid = %s",
        (dest_acct,),
    )
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid destination account '{dest_acct}'")

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_CHECKING} WHERE custid = %s",
        (send_acct,),
    )
    row = cursor.fetchone()
    if not row:
        raise InvalidAccount(
            f"No {TABLENAME_CHECKING} for customer #{send_acct}"
        )
    balance_val = row[0]

    if balance_val < amount:
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
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid account '{acct_id}'")

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_SAVINGS} WHERE custid = %s",
        (acct_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    balance_val = row[0]
    if balance_val - amount < 0:
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
    if not cursor.fetchone():
        raise InvalidAccount(f"Invalid account name '{acct_id}'")

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_SAVINGS} WHERE custid = %s",
        (acct_id,),
    )
    if not cursor.fetchone():
        raise InvalidAccount(f"No {TABLENAME_SAVINGS} for customer #{acct_id}")

    cursor.execute(
        f"SELECT bal FROM {TABLENAME_CHECKING} WHERE custid = %s",
        (acct_id,),
    )
    if not cursor.fetchone():
        raise InvalidAccount(f"No {TABLENAME_CHECKING} for customer #{acct_id}")

    cursor.execute(
        f"UPDATE {TABLENAME_CHECKING} SET bal = bal - %s WHERE custid = %s",
        (amount, acct_id),
    )
    conn.commit()
