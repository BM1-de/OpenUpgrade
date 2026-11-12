# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def resource_calendar_calendar_type(env):
    """
    resource.calendar#schedule_type, #flexible_hours and #two_weeks_calendar are
    replaced by #calendar_type:
    flexible -> undefined, two weeks -> variable, everything else -> fixed
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE resource_calendar
        ADD COLUMN IF NOT EXISTS calendar_type varchar
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar
        SET calendar_type = CASE
            WHEN flexible_hours OR schedule_type = 'flexible' THEN 'undefined'
            WHEN two_weeks_calendar THEN 'variable'
            ELSE 'fixed'
        END
        """,
    )


def resource_calendar_days_per_week(env):
    """
    Fill the new resource.calendar#days_per_week from the working lines of v19
    for all calendars. Odoo only computes it for fixed calendars, on the others
    the user sets it, so the value has to come from the old lines before they
    are removed. Calendars in two weeks mode count the days of an average week.
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE resource_calendar
        ADD COLUMN IF NOT EXISTS days_per_week numeric
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar rc
        SET days_per_week = COALESCE(days.days, 0)
        FROM resource_calendar rc2
        LEFT JOIN (
            SELECT
                calendar_id,
                COUNT(DISTINCT (COALESCE(week_type, '0'), dayofweek))::numeric
                / COUNT(DISTINCT COALESCE(week_type, '0')) AS days
            FROM resource_calendar_attendance
            WHERE
                COALESCE(day_period, '') != 'lunch'
                AND display_type IS NULL
            GROUP BY calendar_id
        ) days ON days.calendar_id = rc2.id
        WHERE rc2.id = rc.id
        """,
    )


def resource_calendar_attendance_cleanup(env):
    """
    Remove the lines that have no meaning in v20: breaks (day_period lunch, in
    v20 a break is the gap between two lines), section lines (display_type) and
    all lines of flexible calendars (undefined calendars have no lines).
    """
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM resource_calendar_attendance rca
        USING resource_calendar rc
        WHERE
            rc.id = rca.calendar_id
            AND (
                rca.day_period = 'lunch'
                OR rca.display_type IS NOT NULL
                OR rc.calendar_type = 'undefined'
            )
        """,
    )


def resource_calendar_attendance_duration_based(env):
    """
    resource.calendar.attendance#duration_based was related to the calendar and
    is computed from the hours now: a line is based on its duration when it has
    neither hour_from nor hour_to. Take the value over from the calendar and
    reset the hours of those lines, v19 centered them around 12:00.
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE resource_calendar_attendance
        ADD COLUMN IF NOT EXISTS duration_based boolean
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar_attendance rca
        SET duration_based = COALESCE(rc.duration_based, FALSE)
        FROM resource_calendar rc
        WHERE rc.id = rca.calendar_id
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar_attendance
        SET hour_from = 0, hour_to = 0
        WHERE duration_based
        """,
    )


def resource_calendar_leaves_count_as(env):
    """
    resource.calendar.leaves#time_type is replaced by #count_as:
    leave -> absence, other -> working_time
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE resource_calendar_leaves
        ADD COLUMN IF NOT EXISTS count_as varchar
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar_leaves
        SET count_as = CASE
            WHEN time_type = 'other' THEN 'working_time' ELSE 'absence'
        END
        """,
    )


def res_company_tz(env):
    """
    The timezone moved from resource.calendar#tz to the new res.company#tz.
    Take it from the default calendar of the company, companies without one
    get the value Odoo computes from their country.
    """
    openupgrade.logged_query(
        env.cr,
        """
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS tz varchar
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_company rc
        SET tz = cal.tz
        FROM resource_calendar cal
        WHERE cal.id = rc.resource_calendar_id AND rc.tz IS NULL
        """,
    )


def resource_resource_calendar_id(env):
    """
    resource.resource#calendar_id is required now, v19 used an empty calendar
    for fully flexible resources. Give those resources one fully flexible
    calendar per company: type undefined without any hours target.
    """
    env.cr.execute(
        """
        SELECT DISTINCT company_id FROM resource_resource
        WHERE calendar_id IS NULL
        """
    )
    for (company_id,) in env.cr.fetchall():
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
        calendar_id = env.cr.fetchone()[0]
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE resource_resource
            SET calendar_id = %s
            WHERE calendar_id IS NULL AND company_id IS NOT DISTINCT FROM %s
            """,
            (calendar_id, company_id),
        )


@openupgrade.migrate()
def migrate(env, version):
    resource_calendar_calendar_type(env)
    resource_calendar_days_per_week(env)
    resource_calendar_attendance_cleanup(env)
    resource_calendar_attendance_duration_based(env)
    resource_calendar_leaves_count_as(env)
    res_company_tz(env)
    resource_resource_calendar_id(env)
