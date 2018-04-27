# -*- coding: utf-8 -*-
# Copyright 2017 Jairo Llopis <jairo.llopis@tecnativa.com>
# Copyright 2018 Ivan Yelizariev <https://it-projects.info/team/yelizariev>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import logging

from odoo import fields, models, api
from odoo.http import request


_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    was_active = fields.Boolean(
        readonly=True,
        help="Indicates if the view was originally active before converting "
             "the single website theme that owns it to multi website mode.",
    )
    origin_view_id = fields.Many2one(
        "ir.ui.view",
        string="Copied from",
        readonly=True,
        help="View from where this one was copied for multi-website"
    )
    multitheme_copy_ids = fields.One2many(
        "ir.ui.view",
        "origin_view_id",
        string="Copies",
        readonly=True,
        help="Duplicates of this view"
    )

    @api.model
    def _customize_template_get_views(self, key, full=False, bundles=False):
        """This method is used to prepare items
           in 'Customize' menu of website Editor"""
        views = super(IrUiView, self)._customize_template_get_views(
            key, full=full, bundles=bundles
        )
        if full:
            return views
        current_website = request.website
        return views.filtered(lambda v: v.website_id == current_website)

    # Workaround for https://github.com/odoo/odoo/pull/24429
    def search(self, domain, offset=0, limit=None, order=None, count=False):
        if self.env.context.get('search_multi_website_snippet'):
            website_id = self.env.context['search_multi_website_snippet']
            domain += [
                '|',
                ('website_id', '=', website_id),
                ('website_id', '=', False)
            ]
            order = 'website_id DESC'
            limit = 1
            _logger.debug('Updated domain: %s', domain)

        res = super(IrUiView, self).search(
            domain, offset=offset, limit=limit, order=order, count=count)

        return res
