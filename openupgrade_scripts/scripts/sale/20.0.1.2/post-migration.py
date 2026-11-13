# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def sale_order_prepayment_percent(env):
    """
    sale.order#require_payment is gone: an order has to be paid online as soon as
    prepayment_percent is positive. Until 19.0 the percentage was filled on every
    order (100 % by default) and only used if require_payment was set. Without
    this, the portal asks the customer to pay every open quotation.
    """
    if openupgrade.column_exists(env.cr, "sale_order", "require_payment"):
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE sale_order
            SET prepayment_percent = 0
            WHERE require_payment IS NOT TRUE AND prepayment_percent != 0
            """,
        )


@openupgrade.migrate()
def migrate(env, version):
    sale_order_prepayment_percent(env)
    openupgrade.load_data(env, "sale", "20.0.1.2/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "sale",
        [
            "email_template_edi_sale",
            "email_template_proforma",
            "mail_template_sale_confirmation",
        ],
        ["body_html", "description", "name", "subject"],
    )
