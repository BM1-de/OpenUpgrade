# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_fields = [
    # the invoice of a timesheet moved from sale_timesheet to sale under a new
    # name, the column has to carry its new name before sale creates the field
    (
        "account.analytic.line",
        "account_analytic_line",
        "timesheet_invoice_id",
        "reinvoice_move_id",
    ),
    ("product.template", "product_template", "expense_policy", "reinvoice_policy"),
]


def sale_order_line_customer_lead(env):
    """
    sale.order.line#customer_lead is an integer now. Convert the column,
    otherwise Odoo moves the float column away and starts with an empty one.
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE sale_order_line
        ALTER COLUMN customer_lead TYPE integer
        USING ROUND(customer_lead)::integer
        """,
    )


def action_accrued_revenue_entry(env):
    """
    sale.action_accrued_revenue_entry_sale_order_line was a window action and
    is a server action now. Remove the old record, Odoo refuses to update a
    record of another model under the same xmlid.
    """
    env.cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE
            module = 'sale'
            AND name = 'action_accrued_revenue_entry_sale_order_line'
            AND model = 'ir.actions.act_window'
        """
    )
    row = env.cr.fetchone()
    if not row:
        return
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE
            module = 'sale'
            AND name = 'action_accrued_revenue_entry_sale_order_line'
            AND model = 'ir.actions.act_window'
        """,
    )
    openupgrade.logged_query(
        env.cr, "DELETE FROM ir_act_window WHERE id = %s", (row[0],)
    )


@openupgrade.migrate()
def migrate(env, version):
    if openupgrade.column_exists(
        env.cr, "account_analytic_line", "timesheet_invoice_id"
    ):
        openupgrade.rename_fields(env, _renamed_fields[:1])
    openupgrade.rename_fields(env, _renamed_fields[1:])
    sale_order_line_customer_lead(env)
    action_accrued_revenue_entry(env)
