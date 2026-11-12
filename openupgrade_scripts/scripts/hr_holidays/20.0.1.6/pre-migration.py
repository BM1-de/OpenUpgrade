# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# xmlid of the global hr.leave.type of v19 (module hr_holidays) -> xmlid of the
# hr.work.entry.type (module hr_work_entry) that hr_holidays configures as its
# replacement in v20, see hr_holidays/data/hr_work_entry_type_data.xml
_global_types = {
    "leave_type_paid_time_off": "generic_work_entry_type_legal_leave",
    "leave_type_sick_time_off": "generic_work_entry_type_sick_leave",
    "leave_type_compensatory_days": "generic_work_entry_type_compensatory",
    "leave_type_unpaid": "generic_work_entry_type_unpaid_leave",
}

_renamed_fields = [
    (
        "hr.leave.allocation",
        "hr_leave_allocation",
        "yearly_accrued_amount",
        "yearly_accrued_days",
    ),
]


def hr_leave_type_work_entry_type(env):
    """
    hr.leave.type is replaced by hr.work.entry.type. Decide for every time off
    type which work entry type takes its place and keep the answer in
    hr_leave_type.work_entry_type_id, post-migration copies the settings.

    - a link that already exists (v19 with hr_work_entry_holidays) is kept
    - the four global types of hr_holidays map to the generic work entry types
      that v20 sets up for time off
    - every other type that is in use or was created by the user gets a work
      entry type of its own. Unused types from the data of hr_holidays are
      dropped, v20 ships its own list per country.

    A work entry type takes the place of only one time off type, because it
    carries the settings of the time off type from now on.
    """
    if not openupgrade.column_exists(env.cr, "hr_leave_type", "work_entry_type_id"):
        openupgrade.logged_query(
            env.cr,
            "ALTER TABLE hr_leave_type ADD COLUMN work_entry_type_id integer",
        )
    # keep an existing link only for the first time off type that uses it
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_leave_type hlt
        SET work_entry_type_id = NULL
        WHERE
            work_entry_type_id IS NOT NULL
            AND EXISTS (
                SELECT 1 FROM hr_leave_type other
                WHERE
                    other.work_entry_type_id = hlt.work_entry_type_id
                    AND other.id < hlt.id
            )
        """,
    )
    for leave_type_name, work_entry_type_name in _global_types.items():
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE hr_leave_type hlt
            SET work_entry_type_id = wet_imd.res_id
            FROM ir_model_data hlt_imd, ir_model_data wet_imd
            WHERE
                hlt.work_entry_type_id IS NULL
                AND hlt_imd.model = 'hr.leave.type'
                AND hlt_imd.module = 'hr_holidays'
                AND hlt_imd.name = %s
                AND hlt_imd.res_id = hlt.id
                AND wet_imd.model = 'hr.work.entry.type'
                AND wet_imd.module = 'hr_work_entry'
                AND wet_imd.name = %s
                AND NOT EXISTS (
                    SELECT 1 FROM hr_leave_type other
                    WHERE other.work_entry_type_id = wet_imd.res_id
                )
            """,
            (leave_type_name, work_entry_type_name),
        )
    in_use = """
        EXISTS (SELECT 1 FROM hr_leave WHERE holiday_status_id = hlt.id)
        OR EXISTS (
            SELECT 1 FROM hr_leave_allocation WHERE holiday_status_id = hlt.id
        )
    """
    if openupgrade.column_exists(env.cr, "hr_leave_accrual_plan", "time_off_type_id"):
        in_use += """
        OR EXISTS (
            SELECT 1 FROM hr_leave_accrual_plan WHERE time_off_type_id = hlt.id
        )
        """
    env.cr.execute(
        f"""
        SELECT hlt.id
        FROM hr_leave_type hlt
        WHERE
            hlt.work_entry_type_id IS NULL
            AND (
                {in_use}
                OR NOT EXISTS (
                    SELECT 1 FROM ir_model_data
                    WHERE
                        model = 'hr.leave.type'
                        AND res_id = hlt.id
                        AND module NOT IN ('__export__', '__import__')
                )
            )
        ORDER BY hlt.id
        """
    )
    for (leave_type_id,) in env.cr.fetchall():
        env.cr.execute(
            """
            INSERT INTO hr_work_entry_type (
                name, code, sequence, color, active, country_id, count_as,
                amount_rate, create_uid, write_uid, create_date, write_date
            )
            SELECT
                name, 'LT' || id, sequence, color, active, country_id,
                CASE WHEN time_type = 'other' THEN 'working_time' ELSE 'absence' END,
                CASE WHEN unpaid THEN 0 ELSE 1 END,
                create_uid, write_uid, create_date, write_date
            FROM hr_leave_type
            WHERE id = %s
            RETURNING id
            """,
            (leave_type_id,),
        )
        openupgrade.logged_query(
            env.cr,
            "UPDATE hr_leave_type SET work_entry_type_id = %s WHERE id = %s",
            (env.cr.fetchone()[0], leave_type_id),
        )


def work_entry_type_id(env):
    """
    Create the new required work_entry_type_id of time off, allocations and
    accrual plans empty. Post-migration fills it, after the work entry types
    are set up: Odoo refuses to change some settings of a type that is in use.
    Creating the column here also keeps Odoo from guessing a type for existing
    allocations.
    """
    for table in ("hr_leave", "hr_leave_allocation", "hr_leave_accrual_plan"):
        openupgrade.logged_query(
            env.cr,
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS work_entry_type_id integer",
        )


def hr_leave_request_duration(env):
    """
    hr.leave#request_unit_hours and #request_unit_half are replaced by
    #request_duration: specific for requests in hours, the half day for a lone
    half day, full for everything else
    """
    openupgrade.logged_query(
        env.cr,
        "ALTER TABLE hr_leave ADD COLUMN IF NOT EXISTS request_duration varchar",
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_leave
        SET request_duration = CASE
            WHEN request_unit_hours THEN 'specific'
            WHEN
                request_unit_half
                AND request_date_from = request_date_to
                AND request_date_from_period = request_date_to_period
            THEN request_date_from_period
            ELSE 'full'
        END
        """,
    )


def hr_leave_type_xmlids(env):
    """
    Remove the xmlids of the obsolete model, the records stay in their table
    """
    openupgrade.logged_query(
        env.cr, "DELETE FROM ir_model_data WHERE model = 'hr.leave.type'"
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
    hr_leave_type_work_entry_type(env)
    work_entry_type_id(env)
    hr_leave_request_duration(env)
    hr_leave_type_xmlids(env)
