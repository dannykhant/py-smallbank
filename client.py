from __future__ import annotations

import random
from typing import Optional, Callable

from constants import (
    FREQUENCY_AMALGAMATE,
    FREQUENCY_BALANCE,
    FREQUENCY_DEPOSIT_CHECKING,
    FREQUENCY_SEND_PAYMENT,
    FREQUENCY_TRANSACT_SAVINGS,
    FREQUENCY_WRITE_CHECK,
    NUM_ACCOUNTS,
    HOTSPOT_PERCENTAGE,
    HOTSPOT_USE_FIXED_SIZE,
    HOTSPOT_FIXED_SIZE,
)
from drivers.mysqldriver import (
    amalgamate,
    balance,
    deposit_checking,
    send_payment,
    transact_savings,
    write_check,
)


class SmallBankClient:
    def __init__(
        self,
        conn_factory: Callable,
        num_accounts: int = NUM_ACCOUNTS,
        scale_factor: float = 1.0,
        hotspot_percentage: float = HOTSPOT_PERCENTAGE,
        hotspot_use_fixed_size: bool = HOTSPOT_USE_FIXED_SIZE,
        hotspot_fixed_size: int = HOTSPOT_FIXED_SIZE,
        prob_account_hotspot: float = 0.0,
        prob_multiaccount_dtxn: float = 50.0,
        force_multisite_dtxns: bool = False,
        force_singlesite_dtxns: bool = False,
        custom_weights: Optional[dict[str, int]] = None,
    ):
        self.conn_factory = conn_factory
        self.num_accounts = int(round(num_accounts * scale_factor))
        self.rand = random.Random()

        self.prob_account_hotspot = prob_account_hotspot
        self.prob_multiaccount_dtxn = prob_multiaccount_dtxn
        self.force_multisite_dtxns = force_multisite_dtxns
        self.force_singlesite_dtxns = force_singlesite_dtxns

        if hotspot_use_fixed_size:
            self.hotspot_size = hotspot_fixed_size
        else:
            self.hotspot_size = int(
                (hotspot_percentage / 100.0) * self.num_accounts
            )

        weights = {
            Transaction.AMALGAMATE: custom_weights.get("Amalgamate")
            if custom_weights
            else None,
            Transaction.BALANCE: custom_weights.get("Balance")
            if custom_weights
            else None,
            Transaction.DEPOSIT_CHECKING: custom_weights.get(
                "DepositChecking"
            )
            if custom_weights
            else None,
            Transaction.SEND_PAYMENT: custom_weights.get("SendPayment")
            if custom_weights
            else None,
            Transaction.TRANSACT_SAVINGS: custom_weights.get(
                "TransactSavings"
            )
            if custom_weights
            else None,
            Transaction.WRITE_CHECK: custom_weights.get("WriteCheck")
            if custom_weights
            else None,
        }

        self.txns: list[Transaction] = []
        for txn in Transaction:
            weight = weights[txn] if weights[txn] is not None else txn.weight
            self.txns.extend([txn] * weight)

        self.rand.shuffle(self.txns)

    def _pick_account_pair(self, needs_two: bool) -> tuple[int, int]:
        while True:
            lo = self.hotspot_size
            hi = self.num_accounts

            acct0 = self.rand.randrange(lo, hi)

            if not needs_two:
                return (acct0, -1)

            acct1 = self.rand.randrange(lo, hi)

            if acct0 != acct1:
                return (acct0, acct1)

    def _pick_transaction(self):
        return self.rand.choice(self.txns)

    def _generate_params(self, txn) -> tuple:
        needs_two = txn in (Transaction.AMALGAMATE, Transaction.SEND_PAYMENT)
        acct0, acct1 = self._pick_account_pair(needs_two)

        if txn == Transaction.AMALGAMATE:
            return (acct0, acct1)
        elif txn == Transaction.BALANCE:
            return (acct0,)
        elif txn == Transaction.DEPOSIT_CHECKING:
            return (acct0, 1.3)
        elif txn == Transaction.SEND_PAYMENT:
            return (acct0, acct1, 5.00)
        elif txn == Transaction.TRANSACT_SAVINGS:
            return (acct0, 20.20)
        elif txn == Transaction.WRITE_CHECK:
            return (acct0, 5.0)

    def run_once(self, conn) -> str:
        txn = self._pick_transaction()
        params = self._generate_params(txn)
        txn.func(conn, *params)
        return txn.name

    def run(self, num_txns: int, progress_callback=None):
        conn = self.conn_factory()
        import time as _time
        counts: dict[str, int] = {}
        latencies: dict[str, float] = {}
        for _ in range(num_txns):
            txn = self._pick_transaction()
            params = self._generate_params(txn)
            start = _time.perf_counter()
            try:
                txn.func(conn, *params)
                name = txn.name
            except Exception:
                name = "ERROR"
            elapsed = _time.perf_counter() - start
            counts[name] = counts.get(name, 0) + 1
            latencies[name] = latencies.get(name, 0.0) + elapsed
            if progress_callback:
                progress_callback(counts, latencies)
        conn.close()
        return {"counts": counts, "latencies": latencies}


class _TransactionRegistry(type):
    def __iter__(cls):
        return iter(cls._instances)


class Transaction(metaclass=_TransactionRegistry):
    _instances: list[Transaction] = []

    def __init__(self, name: str, weight: int, func: Callable):
        self.name = name
        self.weight = weight
        self.func = func
        Transaction._instances.append(self)


Transaction.AMALGAMATE = Transaction(
    "AMALGAMATE", FREQUENCY_AMALGAMATE, amalgamate
)
Transaction.BALANCE = Transaction("BALANCE", FREQUENCY_BALANCE, balance)
Transaction.DEPOSIT_CHECKING = Transaction(
    "DEPOSIT_CHECKING", FREQUENCY_DEPOSIT_CHECKING, deposit_checking
)
Transaction.SEND_PAYMENT = Transaction(
    "SEND_PAYMENT", FREQUENCY_SEND_PAYMENT, send_payment
)
Transaction.TRANSACT_SAVINGS = Transaction(
    "TRANSACT_SAVINGS", FREQUENCY_TRANSACT_SAVINGS, transact_savings
)
Transaction.WRITE_CHECK = Transaction(
    "WRITE_CHECK", FREQUENCY_WRITE_CHECK, write_check
)
