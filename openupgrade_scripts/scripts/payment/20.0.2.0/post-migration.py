# Copyright 2026 Baumgärtner Marketing GmbH
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


def payment_provider_state(env):
    """
    payment.provider#state (disabled, enabled, test) is gone. A provider is
    live or in test mode (is_live), and it is switched off by archiving it.
    Disabled providers whose module is not installed stay as they are, like
    in a fresh database: they cannot be used without their module.
    """
    if not openupgrade.column_exists(env.cr, "payment_provider", "state"):
        return
    openupgrade.logged_query(
        env.cr, "UPDATE payment_provider SET is_live = (state = 'enabled')"
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE payment_provider pp
        SET active = FALSE
        WHERE
            pp.state = 'disabled'
            AND (
                pp.module_id IS NULL
                OR pp.module_id IN (
                    SELECT id FROM ir_module_module WHERE state = 'installed'
                )
            )
        """,
    )


def payment_method_without_provider(env):
    """
    A payment method belongs to one provider now (provider_id, required) and
    is created with the module of its provider. The generic methods of the
    previous version, shared between providers, have no place any more.

    Methods that no token and no transaction refers to are removed, which
    leaves the database like a fresh one. The others are kept and reported:
    they still need a provider.
    """
    env.cr.execute(
        """
        WITH used AS (
            SELECT payment_method_id AS id FROM payment_token
            WHERE payment_method_id IS NOT NULL
            UNION
            SELECT payment_method_id FROM payment_transaction
            WHERE payment_method_id IS NOT NULL
        ),
        kept AS (
            SELECT id FROM used
            UNION
            SELECT pm.primary_payment_method_id
            FROM payment_method pm
            JOIN used ON used.id = pm.id
            WHERE pm.primary_payment_method_id IS NOT NULL
        )
        SELECT pm.id, pm.id IN (SELECT id FROM kept)
        FROM payment_method pm
        WHERE pm.provider_id IS NULL
        """
    )
    rows = env.cr.fetchall()
    unused_ids = [row[0] for row in rows if not row[1]]
    used_ids = [row[0] for row in rows if row[1]]
    if used_ids:
        _logger.warning(
            "%s payment methods are used by tokens or transactions and have no "
            "provider yet: %s",
            len(used_ids),
            used_ids,
        )
    if unused_ids:
        # Plain SQL: unlink() refuses to delete the generic method "unknown",
        # and the framework would swallow that error for the whole batch.
        ids = tuple(unused_ids)
        env.cr.execute(
            """
            SELECT id FROM ir_attachment
            WHERE res_model = 'payment.method' AND res_id IN %s
            """,
            (ids,),
        )
        env["ir.attachment"].browse(row[0] for row in env.cr.fetchall()).unlink()
        openupgrade.logged_query(
            env.cr,
            "DELETE FROM ir_model_data WHERE model = 'payment.method' AND res_id IN %s",
            (ids,),
        )
        # brands first, they point to their primary method
        openupgrade.logged_query(
            env.cr,
            """
            DELETE FROM payment_method
            WHERE id IN %s AND primary_payment_method_id IS NOT NULL
            """,
            (ids,),
        )
        openupgrade.logged_query(
            env.cr, "DELETE FROM payment_method WHERE id IN %s", (ids,)
        )
        env["payment.method"].invalidate_model()


@openupgrade.migrate()
def migrate(env, version):
    payment_provider_state(env)
    payment_method_without_provider(env)
