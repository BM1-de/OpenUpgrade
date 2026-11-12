# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def hr_attendance_state(env):
    """
    hr.attendance has a required state now and only validated attendances
    count. Every attendance of v19 counted as worked time, whatever the status
    of its overtime was, so all of them are validated. Without this the field
    takes its default draft.
    """
    openupgrade.logged_query(
        env.cr,
        "ALTER TABLE hr_attendance ADD COLUMN IF NOT EXISTS state varchar",
    )
    openupgrade.logged_query(
        env.cr,
        "UPDATE hr_attendance SET state = 'validated' WHERE state IS NULL",
    )


def res_company_attendance_validation(env):
    """
    res.company#attendance_overtime_validation is replaced by
    #attendance_validation: approval by the manager becomes manual validation
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS attendance_validation varchar
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_company
        SET attendance_validation = CASE
            WHEN attendance_overtime_validation = 'by_manager'
            THEN 'manual_validation'
            ELSE 'no_validation'
        END
        WHERE attendance_validation IS NULL
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    # The overtime of v19 (hr.attendance.overtime.line, .rule and .ruleset, the
    # overtime fields of hr.attendance and hr.version#ruleset_id) has no
    # counterpart that could be filled by a query: v20 derives overtime from
    # time rules (hr.time.rule) as attendances of their own and keeps no signed
    # balance. The tables and columns of v19 are kept untouched.
    hr_attendance_state(env)
    res_company_attendance_validation(env)
