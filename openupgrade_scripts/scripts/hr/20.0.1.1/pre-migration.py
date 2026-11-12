# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_renamed_models = [
    ("hr.contract.type", "hr.employee.type"),
]

_renamed_tables = [
    ("hr_contract_type", "hr_employee_type"),
]

_renamed_fields = [
    ("hr.job", "hr_job", "contract_type_id", "employee_type_id"),
    ("hr.version", "hr_version", "contract_type_id", "employee_type_id"),
]

_copied_columns = {
    "hr_version": [
        ("sex", None, None),
    ],
}

_renamed_columns = {
    # the selection is replaced by hr.version#employee_type_id, which already
    # holds the contract type of v19. Post-migration fills the gaps from here.
    "hr_version": [
        ("employee_type", None),
    ],
}


def hr_employee_additional_note(env):
    """
    hr.employee#additional_note was related to the current version and is a
    field of the employee now
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE hr_employee
        ADD COLUMN IF NOT EXISTS additional_note text
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_employee he
        SET additional_note = hv.additional_note
        FROM hr_version hv
        WHERE hv.id = he.current_version_id AND hv.additional_note IS NOT NULL
        """,
    )


def hr_employee_contract_template_id(env):
    """
    hr.employee#contract_template_id was related to the current version and is
    a field of the employee now
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE hr_employee
        ADD COLUMN IF NOT EXISTS contract_template_id integer
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_employee he
        SET contract_template_id = hv.contract_template_id
        FROM hr_version hv
        WHERE hv.id = he.current_version_id
            AND hv.contract_template_id IS NOT NULL
        """,
    )


def hr_version_tz(env):
    """
    hr.version#tz was related to the employee (the timezone of its resource)
    and is a required field of the version now. Versions without employee are
    contract templates, they get the timezone of their company.
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE hr_version
        ADD COLUMN IF NOT EXISTS tz varchar
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_version hv
        SET tz = rr.tz
        FROM hr_employee he
        JOIN resource_resource rr ON rr.id = he.resource_id
        WHERE he.id = hv.employee_id AND hv.tz IS NULL
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_version hv
        SET tz = COALESCE(rc.tz, 'UTC')
        FROM hr_version hv2
        LEFT JOIN res_company rc ON rc.id = hv2.company_id
        WHERE hv2.id = hv.id AND hv.tz IS NULL
        """,
    )


def hr_version_resource_calendar_id(env):
    """
    hr.version#resource_calendar_id is required now, v19 used an empty calendar
    for fully flexible employees. Give those versions one fully flexible
    calendar per company: type undefined without any hours target.
    """
    env.cr.execute(
        """
        SELECT DISTINCT company_id FROM hr_version
        WHERE resource_calendar_id IS NULL
        """
    )
    for (company_id,) in env.cr.fetchall():
        env.cr.execute(
            """
            SELECT id FROM resource_calendar
            WHERE
                calendar_type = 'undefined'
                AND COALESCE(hours_per_week, 0) = 0
                AND COALESCE(hours_per_day, 0) = 0
                AND company_id IS NOT DISTINCT FROM %s
            ORDER BY active DESC, id
            LIMIT 1
            """,
            (company_id,),
        )
        row = env.cr.fetchone()
        if not row:
            env.cr.execute(
                """
                INSERT INTO resource_calendar (
                    name, company_id, calendar_type, active,
                    hours_per_day, hours_per_week, days_per_week,
                    full_time_required_hours, create_uid, write_uid,
                    create_date, write_date
                )
                VALUES (
                    'Fully flexible', %s, 'undefined', TRUE, 0, 0, 0, 0, 1, 1,
                    NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
                )
                RETURNING id
                """,
                (company_id,),
            )
            row = env.cr.fetchone()
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE hr_version
            SET resource_calendar_id = %s
            WHERE
                resource_calendar_id IS NULL
                AND company_id IS NOT DISTINCT FROM %s
            """,
            (row[0], company_id),
        )


def hr_version_sex(env):
    """
    hr.version#sex lost its value other, the legal sex is male or female now
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_version SET sex = NULL WHERE sex = 'other'
        """,
    )


def hr_job_company_id(env):
    """
    hr.job#company_id is required now. Jobs without company were shared by all
    companies in v19: assign the company of their department, otherwise the
    company most employees of the job work for, otherwise the first company.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_job hj
        SET company_id = hd.company_id
        FROM hr_department hd
        WHERE
            hj.company_id IS NULL
            AND hd.id = hj.department_id
            AND hd.company_id IS NOT NULL
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE hr_job hj
        SET company_id = COALESCE(
            (
                SELECT hv.company_id FROM hr_version hv
                WHERE hv.job_id = hj.id AND hv.company_id IS NOT NULL
                GROUP BY hv.company_id
                ORDER BY COUNT(*) DESC, hv.company_id
                LIMIT 1
            ),
            (SELECT MIN(id) FROM res_company)
        )
        WHERE hj.company_id IS NULL
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_models(env.cr, _renamed_models)
    openupgrade.rename_tables(env.cr, _renamed_tables)
    openupgrade.rename_fields(env, _renamed_fields)
    openupgrade.copy_columns(env.cr, _copied_columns)
    openupgrade.rename_columns(env.cr, _renamed_columns)
    hr_employee_additional_note(env)
    hr_employee_contract_template_id(env)
    hr_version_tz(env)
    hr_version_resource_calendar_id(env)
    hr_version_sex(env)
    hr_job_company_id(env)
