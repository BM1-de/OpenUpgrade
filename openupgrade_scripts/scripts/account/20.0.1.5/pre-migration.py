# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def account_payment_state(env):
    """
    The states of a payment moved one step: what was "in_process" (posted, not
    matched with the bank yet) is "paid" now, and what was "paid" is
    "reconciled". Both in one statement, the values overlap.

    This is the starting point only: payments booked directly on a bank or cash
    account stay "paid" in this version. post-migration lets Odoo compute the
    state again.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_payment
        SET state = CASE state
            WHEN 'paid' THEN 'reconciled'
            WHEN 'in_process' THEN 'paid'
        END
        WHERE state IN ('paid', 'in_process')
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    account_payment_state(env)
