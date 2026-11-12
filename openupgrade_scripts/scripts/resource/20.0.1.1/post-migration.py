# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def resource_calendar_attendance_day_period(env):
    """
    resource.calendar.attendance#day_period is computed in v20 and knows the
    new value full_day. Recompute it for the lines kept from v19.
    """
    attendances = env["resource.calendar.attendance"].search([])
    env.add_to_compute(attendances._fields["day_period"], attendances)
    attendances.flush_recordset(["day_period"])


@openupgrade.migrate()
def migrate(env, version):
    resource_calendar_attendance_day_period(env)
    openupgrade.load_data(env, "resource", "20.0.1.1/noupdate_changes.xml")
