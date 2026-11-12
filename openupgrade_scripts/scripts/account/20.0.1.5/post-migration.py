# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def account_move_review_state(env):
    """
    account.move#checked became review_state, and reviewing is a setting of
    the company now (set_to_review_documents). Before, every entry posted by
    someone who is not an accountant was waiting for a review.

    Companies with posted entries waiting for a review keep working that way:
    the setting is switched on, unchecked entries are to review, checked ones
    reviewed. All other companies keep the default (no review).
    """
    if not openupgrade.column_exists(env.cr, "account_move", "checked"):
        return
    env.cr.execute(
        """
        SELECT DISTINCT company_id FROM account_move
        WHERE state = 'posted' AND checked IS NOT TRUE
        """
    )
    company_ids = tuple(row[0] for row in env.cr.fetchall())
    if not company_ids:
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_move
        SET review_state = CASE WHEN checked THEN 'reviewed' ELSE 'todo' END
        WHERE state = 'posted' AND company_id IN %s
        """,
        (company_ids,),
    )
    openupgrade.logged_query(
        env.cr,
        "UPDATE res_company SET set_to_review_documents = TRUE WHERE id IN %s",
        (company_ids,),
    )


def account_payment_state(env):
    """
    Compute the state of the posted payments again, after pre-migration has
    renamed the values. A payment whose liquidity line is on a bank or cash
    account that is not reconciled used to be "paid" and is "paid" again; only
    payments matched with the bank are "reconciled".
    """
    # no tracking: the chatter of a payment should not tell that its state
    # changed on the day of the upgrade
    payments = (
        env["account.payment"]
        .with_context(active_test=False, tracking_disable=True)
        .search([("state", "in", ("paid", "reconciled"))])
    )
    for name in ("state", "is_reconciled", "is_matched"):
        env.add_to_compute(payments._fields[name], payments)
    payments.flush_recordset(["state", "is_reconciled", "is_matched"])


def account_move_line_deductible_percentage(env):
    """
    account.move.line#deductible_amount (0 to 100) became
    deductible_percentage (0 to 1). New rows default to 1.
    """
    if not openupgrade.column_exists(env.cr, "account_move_line", "deductible_amount"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_move_line
        SET deductible_percentage = deductible_amount / 100.0
        WHERE deductible_amount IS NOT NULL AND deductible_amount != 100
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    account_move_review_state(env)
    account_payment_state(env)
    account_move_line_deductible_percentage(env)
