# -*- coding: utf-8 -*-
# Copyright 2015 Antiun Ingenieria S.L. - Antonio Espinosa
# Copyright 2017 Jairo Llopis <jairo.llopis@tecnativa.com>
# Copyright 2018 Ivan Yelizariev <https://it-projects.info/team/yelizariev>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import logging

from lxml import etree
from odoo import api, models, fields
from odoo.tools import config


MODULE = "website_multi_theme"
LAYOUT_KEY = MODULE + ".auto_layout_website_%d"
ASSETS_KEY = MODULE + ".auto_assets_website_%d"
VIEW_KEY = MODULE + ".auto_view_%d_%d"
_logger = logging.getLogger(__name__)


class Website(models.Model):
    _inherit = "website"

    multi_theme_id = fields.Many2one(
        string="Multiwebsite theme",
        comodel_name='website.theme',
        domain=[("asset_ids.view_id", "!=", False)],
        help="Multiwebsite-compatible theme for this website",
        require=True,
        default=lambda self: self.env.ref('website_multi_theme.theme_default',
                                          raise_if_not_found=False)
    )
    multi_theme_view_ids = fields.One2many(
        comodel_name="ir.ui.view",
        inverse_name="website_id",
        domain=[("origin_view_id", "!=", False),
                "|", ("active", "=", True), ("active", "=", False)],
        string="Multiwebsite views",
        help="Views generated by the multiwebsite theme just for this website",
    )

    @api.model
    def create(self, vals):
        result = super(Website, self).create(vals)
        if "multi_theme_id" in vals:
            result._multi_theme_activate()
        return result

    def write(self, vals):
        result = super(Website, self).write(vals)
        if "multi_theme_id" in vals:
            self._multi_theme_activate()
        return result

    def _find_duplicate_view_for_website(self, origin_view, website):
        xmlid = VIEW_KEY % (website.id, origin_view.id)
        return self.env.ref(xmlid, raise_if_not_found=False)

    def _duplicate_view_for_website(self, pattern, xmlid, override_key):
        """Duplicate a view pattern and enable it only for current website.

        :param ir.ui.view pattern:
            Original view that will be copied for current website.

        :param str xmlid:
            The XML ID of the generated record.

        :param bool override_key:
            Indicates wether the view key should be overriden. If ``True``,
            it will become the same as :param:`xmlid`. Otherwise, the key will
            be copied from :param:`pattern` as it would happen normally.

        :return ir.ui.view:
            The duplicated view.
        """
        self.ensure_one()
        # Return the pre-existing copy if any
        try:
            result = self.env.ref(xmlid)
        except ValueError:
            pass
        else:
            # If we develop and want xml reloading, update view arch always
            if "xml" in config.get("dev_mode"):
                result.arch = pattern.arch
            return result
        # Copy patterns only for current website
        key = xmlid if override_key else pattern.key
        result = pattern.with_context(
            duplicate_view_for_website=True
        ).copy({
            "active": pattern.was_active,
            "arch_fs": False,
            "key": key,
            "name": '%s (Website #%s)' % (pattern.name, self.id),
            "website_id": self.id,
            "origin_view_id": pattern.id,
        })
        # Assign external IDs to new views
        module, name = xmlid.split(".")
        self.env["ir.model.data"].create({
            "model": result._name,
            "module": module,
            "name": name,
            "noupdate": True,
            "res_id": result.id,
        })
        _logger.debug(
            "Duplicated %s as %s with xmlid %s for %s with arch:\n%s",
            pattern.display_name,
            result.display_name,
            xmlid,
            self.display_name,
            result.arch,
        )
        return result

    def _multi_theme_activate(self):
        """Activate current multi theme for current websites."""
        main_assets_frontend = (
            self.env.ref("web.assets_frontend") |
            self.env.ref("website.assets_frontend"))
        main_layout = self.env.ref("website.layout")
        main_views = main_assets_frontend | main_layout
        # Patterns that will be duplicated to enable multi themes
        assets_pattern = self.env.ref("website_multi_theme.assets_pattern")
        layout_pattern = self.env.ref("website_multi_theme.layout_pattern")
        for website in self:
            if not website.multi_theme_id:
                default_theme = self.env.ref(
                    'website_multi_theme.theme_default',
                    raise_if_not_found=False,
                )
                if not default_theme:
                    _logger.info(
                        "Deleting multi website theme views for %s: %s",
                        website.display_name,
                        website.multi_theme_view_ids,
                    )
                    website.multi_theme_view_ids.unlink()
                    continue
                else:
                    website.multi_theme_id = default_theme

            # Duplicate multi theme patterns for this website
            custom_assets = website._duplicate_view_for_website(
                assets_pattern,
                ASSETS_KEY % website.id,
                True
            )
            custom_layout = website._duplicate_view_for_website(
                layout_pattern,
                LAYOUT_KEY % website.id,
                True
            )
            # Update custom base views arch to latest pattern
            custom_assets.arch = assets_pattern.arch
            custom_layout.arch = layout_pattern.arch.format(
                theme_view=custom_assets.key,
            )
            # These custom base views must be active
            custom_views = custom_assets | custom_layout
            custom_views.update({
                "active": True,
            })
            # Duplicate all theme's views for this website
            for origin_view in website.mapped(
                    "multi_theme_id.asset_ids.view_id"):
                copied_view = website._duplicate_view_for_website(
                    origin_view,
                    VIEW_KEY % (website.id, origin_view.id),
                    False
                )
                # Applied views must inherit from custom assets or layout
                new_parent = None
                if copied_view.inherit_id & main_views:
                    if copied_view.inherit_id & main_assets_frontend:
                        new_parent = custom_assets
                    elif copied_view.inherit_id & main_layout:
                        new_parent = custom_layout
                else:
                    parent_view = copied_view.inherit_id

                    # check if parent was copied, so we need inherit that
                    # instead of original parent, which is deactivated and not
                    # used
                    copied_parent = self._find_duplicate_view_for_website(
                        parent_view, website
                    )

                    if copied_parent:
                        new_parent = copied_parent

                if new_parent:
                    copied_view.inherit_id = new_parent

                    data = etree.fromstring(copied_view.arch)
                    data.attrib["inherit_id"] = new_parent.key
                    copied_view.arch = etree.tostring(data)

                custom_views |= copied_view
            # Delete any custom view that should exist no more
            (website.multi_theme_view_ids - custom_views).unlink()
            _logger.info(
                "Updated multi website theme views for %s: %s",
                website.display_name,
                website.multi_theme_view_ids,
            )
