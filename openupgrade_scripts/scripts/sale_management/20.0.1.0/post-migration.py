# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # sale.order.template#require_payment is gone, see sale.order in the scripts of sale
    if openupgrade.column_exists(env.cr, "sale_order_template", "require_payment"):
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE sale_order_template
            SET prepayment_percent = 0
            WHERE require_payment IS NOT TRUE AND prepayment_percent != 0
            """,
        )
