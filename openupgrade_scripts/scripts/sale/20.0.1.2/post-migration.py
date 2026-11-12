# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
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
