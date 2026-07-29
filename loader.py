from __future__ import annotations

import math
import random
import concurrent.futures as cf
from typing import Optional

from constants import (
    TABLENAME_ACCOUNTS,
    TABLENAME_SAVINGS,
    TABLENAME_CHECKING,
    NUM_ACCOUNTS,
    MIN_BALANCE,
    MAX_BALANCE,
    BATCH_SIZE,
)


class SmallBankLoader:
    def __init__(
        self,
        conn_factory=None,
        num_accounts: int = NUM_ACCOUNTS,
        scale_factor: float = 1.0,
        load_threads: Optional[int] = None,
    ):
        self.conn_factory = conn_factory
        self.num_accounts = int(round(num_accounts * scale_factor))
        self._cust_name_length = 64

    def _generate_balance(self) -> int:
        range_size = (MAX_BALANCE - MIN_BALANCE) + 1
        while True:
            g = (random.gauss(0, 1) + 2.0) / 4.0
            v = int(round(g * range_size))
            if 0 <= v < range_size:
                break
        return MIN_BALANCE + v

    def _load_range(self, start: int, stop: int, conn_factory):
        conn = conn_factory()
        cursor = conn.cursor()

        acct_fmt = f"%0{self._cust_name_length}d"
        acct_sql = f"INSERT INTO {TABLENAME_ACCOUNTS} (custid, name) VALUES (%s, %s)"
        savings_sql = f"INSERT INTO {TABLENAME_SAVINGS} (custid, bal) VALUES (%s, %s)"
        checking_sql = f"INSERT INTO {TABLENAME_CHECKING} (custid, bal) VALUES (%s, %s)"

        acct_rows: list[tuple] = []
        savings_rows: list[tuple] = []
        checking_rows: list[tuple] = []

        for acct_id in range(start, stop):
            acct_rows.append((acct_id, acct_fmt % acct_id))
            savings_rows.append((acct_id, self._generate_balance()))
            checking_rows.append((acct_id, self._generate_balance()))

            if len(acct_rows) >= BATCH_SIZE:
                cursor.executemany(acct_sql, acct_rows)
                cursor.executemany(savings_sql, savings_rows)
                cursor.executemany(checking_sql, checking_rows)
                conn.commit()
                acct_rows.clear()
                savings_rows.clear()
                checking_rows.clear()

        if acct_rows:
            cursor.executemany(acct_sql, acct_rows)
            cursor.executemany(savings_sql, savings_rows)
            cursor.executemany(checking_sql, checking_rows)
            conn.commit()

        conn.close()

    def load(self):
        num_threads = max(1, int(math.ceil(self.num_accounts / 100000)))
        rows_per_thread = int(math.ceil(self.num_accounts / num_threads))

        futures = []
        with cf.ThreadPoolExecutor(max_workers=num_threads) as pool:
            for i in range(num_threads):
                start = rows_per_thread * i
                stop = min(start + rows_per_thread, self.num_accounts)
                if start >= stop:
                    break
                futures.append(
                    pool.submit(self._load_range, start, stop, self.conn_factory)
                )
        for f in cf.as_completed(futures):
            f.result()
