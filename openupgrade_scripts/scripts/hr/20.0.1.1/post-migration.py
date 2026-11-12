# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# value of the selection hr.version#employee_type of v19 -> xmlid of the
# hr.employee.type that takes its place, or the name of a type to create
_employee_types = {
    "employee": "hr.contract_type_employee",
    "student": "hr.contract_type_student",
    "trainee": "hr.contract_type_intern",
    "worker": "Worker",
    "contractor": "Contractor",
    "freelance": "Freelancer",
}


def hr_version_employee_type_id(env):
    """
    hr.version#employee_type_id replaces both the contract type and the
    selection employee_type of v19. The contract type was renamed to it in
    pre-migration, fill the versions without contract type from the selection.
    """
    legacy_column = openupgrade.get_legacy_name("employee_type")
    env.cr.execute(
        f"""
        SELECT DISTINCT {legacy_column} FROM hr_version
        WHERE employee_type_id IS NULL AND {legacy_column} IS NOT NULL
        """
    )
    for (employee_type,) in env.cr.fetchall():
        target = _employee_types.get(employee_type)
        if not target:
            continue
        if "." in target:
            employee_type_record = env.ref(target, raise_if_not_found=False)
            if not employee_type_record:
                continue
        else:
            employee_type_record = env["hr.employee.type"].search(
                [("name", "=", target)], limit=1
            ) or env["hr.employee.type"].create({"name": target})
        openupgrade.logged_query(
            env.cr,
            f"""
            UPDATE hr_version
            SET employee_type_id = %s
            WHERE employee_type_id IS NULL AND {legacy_column} = %s
            """,
            (employee_type_record.id, employee_type),
        )


def hr_version_fixed_term(env):
    """
    Set the new hr.version#fixed_term for contracts with an end date
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_version
        SET fixed_term = TRUE
        WHERE contract_date_end IS NOT NULL
        """,
    )


def hr_employee_departure(env):
    """
    The departure fields of hr.version moved to the new model
    hr.employee.departure. Create a departure for every version that has a
    departure reason or date and link it.

    v19 never archived an employee by itself, v20 does it with a cron once the
    departure date is reached. Departures in the past are marked as applied, so
    the cron leaves those employees as they are. Departures in the future stay
    planned and are applied by the cron when their date comes.
    """
    env.cr.execute("SELECT MIN(id) FROM hr_departure_reason")
    default_reason_id = env.cr.fetchone()[0]
    if not default_reason_id:
        return
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE hr_employee_departure
        ADD COLUMN IF NOT EXISTS openupgrade_legacy_20_0_version_id integer
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        INSERT INTO hr_employee_departure (
            employee_id, departure_reason_id, departure_description,
            dismissal_date, departure_date, apply_date,
            last_contract_date_end, openupgrade_legacy_20_0_version_id,
            create_uid, write_uid, create_date, write_date
        )
        SELECT
            hv.employee_id,
            COALESCE(hv.departure_reason_id, %s),
            hv.departure_description,
            COALESCE(hv.departure_date, hv.write_date::date),
            COALESCE(hv.departure_date, hv.write_date::date),
            CASE
                WHEN COALESCE(hv.departure_date, hv.write_date::date)
                    < CURRENT_DATE
                THEN COALESCE(hv.departure_date, hv.write_date::date)
            END,
            hv.contract_date_end, hv.id,
            hv.write_uid, hv.write_uid, hv.write_date, hv.write_date
        FROM hr_version hv
        WHERE
            hv.employee_id IS NOT NULL
            AND (
                hv.departure_reason_id IS NOT NULL
                OR hv.departure_date IS NOT NULL
            )
        """,
        (default_reason_id,),
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_version hv
        SET departure_id = hed.id
        FROM hr_employee_departure hed
        WHERE hed.openupgrade_legacy_20_0_version_id = hv.id
        """,
    )


def hr_job_recruiter_id(env):
    """
    hr.job#user_id (a user) is replaced by hr.job#recruiter_id (an employee):
    take the employee of the user in the company of the job
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_job hj
        SET recruiter_id = (
            SELECT he.id FROM hr_employee he
            WHERE he.user_id = hj.user_id
            ORDER BY (he.company_id = hj.company_id) DESC, he.active DESC, he.id
            LIMIT 1
        )
        WHERE hj.user_id IS NOT NULL AND hj.recruiter_id IS NULL
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr", "20.0.1.1/noupdate_changes.xml")
    hr_version_employee_type_id(env)
    hr_version_fixed_term(env)
    hr_employee_departure(env)
    hr_job_recruiter_id(env)
