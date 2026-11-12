# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def account_analytic_line_billable_type(env):
    """
    account.analytic.line#timesheet_invoice_type became billable_type, a field
    of sale_project with new values. sale_project computes it while it is
    loaded, before sale_timesheet adds its own rules, so every timesheet ends
    up as "other costs". Take the type of the timesheets (the lines with a
    project) from the old column instead.

    "timesheet_revenues" has no counterpart any more, such lines are plain
    timesheets billed on time now. Lines without a project keep what
    sale_project computed, their types have been redefined.
    """
    if not openupgrade.column_exists(
        env.cr, "account_analytic_line", "timesheet_invoice_type"
    ):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_analytic_line
        SET
            billable_type = CASE timesheet_invoice_type
                WHEN 'billable_time' THEN '04_billable_time'
                WHEN 'timesheet_revenues' THEN '04_billable_time'
                WHEN 'billable_fixed' THEN '02_billable_fixed'
                WHEN 'billable_milestones' THEN '06_billable_milestones'
                WHEN 'billable_manual' THEN '08_billable_manual'
                WHEN 'non_billable' THEN '09_non_billable'
            END,
            category_report = 'costs'
        WHERE project_id IS NOT NULL
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "sale_timesheet", "20.0.1.0/noupdate_changes.xml")
    account_analytic_line_billable_type(env)
