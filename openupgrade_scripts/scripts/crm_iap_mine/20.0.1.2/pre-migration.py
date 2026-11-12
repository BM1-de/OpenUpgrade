# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def crm_iap_lead_industry(env):
    """
    The industries of v19 (groups of ids of the former data provider in
    reveal_ids) are replaced by a list based on SIC major groups with required
    sic_group and division_id. The old records cannot be mapped to the new
    classification and clash with the unique names of the new ones, so remove
    them and let the module load its new list. Lead mining requests lose their
    industry criteria.
    """
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM crm_iap_lead_industry_crm_iap_lead_mining_request_rel
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE model = 'crm.iap.lead.industry'
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM crm_iap_lead_industry
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    crm_iap_lead_industry(env)
