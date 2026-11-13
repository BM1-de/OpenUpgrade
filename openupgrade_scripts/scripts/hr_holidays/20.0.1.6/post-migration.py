# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

from odoo import Command

# settings of hr.leave.type that exist with the same name and meaning on
# hr.work.entry.type
_copied_settings = [
    "name",
    "sequence",
    "color",
    "leave_validation_type",
    "allocation_validation_type",
    "requires_allocation",
    "employee_requests",
    "request_unit",
    "unpaid",
    "include_public_holidays_in_duration",
    "leave_notif_subtype_id",
    "allocation_notif_subtype_id",
    "support_document",
    "allow_request_on_top",
    "elligible_for_accrual_rate",
    "allows_negative",
    "max_allowed_negative",
    "create_calendar_meeting",
    "hide_on_dashboard",
]


def hr_work_entry_type_defaults(env):
    """
    Set up the work entry types for time off the way an installation of
    hr_holidays does. The module does that with functions and with records in
    noupdate data, both are skipped when the module is updated.
    """
    openupgrade.load_data(env, "hr_holidays", "data/hr_work_entry_type_data.xml")
    # the next steps write with queries: send the pending writes of the data
    # file to the database first, otherwise they overwrite the queries later
    env.flush_all()
    env.invalidate_all()


def hr_work_entry_type_settings(env):
    """
    Copy the settings of every time off type to the work entry type that takes
    its place (see pre-migration). Allocations were counted in hours for types
    requested by hour, in days for all others. An archived time off type is no
    longer selectable for time off.
    """
    columns = [
        column
        for column in _copied_settings
        if openupgrade.column_exists(env.cr, "hr_leave_type", column)
    ]
    assignments = ",\n            ".join(
        f"{column} = hlt.{column}" for column in columns
    )
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE hr_work_entry_type wet
        SET
            {assignments},
            unit_of_measure = CASE
                WHEN hlt.request_unit = 'hour' THEN 'hour' ELSE 'day'
            END,
            time_off_selectable = COALESCE(hlt.active, TRUE)
        FROM hr_leave_type hlt
        WHERE hlt.work_entry_type_id = wet.id
        """,
    )


def work_entry_type_id(env):
    """
    Fill the new required work_entry_type_id of time off, allocations and
    accrual plans from the time off type they had
    """
    for table, column in (
        ("hr_leave", "holiday_status_id"),
        ("hr_leave_allocation", "holiday_status_id"),
        ("hr_leave_accrual_plan", "time_off_type_id"),
    ):
        if not openupgrade.column_exists(env.cr, table, column):
            continue
        openupgrade.logged_query(
            env.cr,
            f"""
            UPDATE {table} t
            SET work_entry_type_id = hlt.work_entry_type_id
            FROM hr_leave_type hlt
            WHERE hlt.id = t.{column}
            """,
        )


def res_groups_employee(env):
    """
    Until 19.0 every internal user could request time off and see the own
    allocations: the access rights belonged to base.group_user. In 20.0 they
    belong to the new group hr_holidays.group_hr_holidays_employee. Internal
    users keep what they had; new users get the group by default as in a fresh
    database (base.default_user_group is noupdate, the update of the module does
    not touch it).
    """
    group = env.ref("hr_holidays.group_hr_holidays_employee")
    users = (
        env["res.users"].with_context(active_test=False).search([("share", "=", False)])
    )
    group.write({"user_ids": [Command.link(user.id) for user in users]})
    env.ref("base.default_user_group").write({"implied_ids": [Command.link(group.id)]})


@openupgrade.migrate()
def migrate(env, version):
    res_groups_employee(env)
    hr_work_entry_type_defaults(env)
    hr_work_entry_type_settings(env)
    work_entry_type_id(env)
