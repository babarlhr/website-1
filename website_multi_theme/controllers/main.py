# Copyright 2018 Ivan Yelizariev <https://it-projects.info/team/yelizariev>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo.http import request, route
from odoo.addons.website.controllers.main import Website


class WebsiteMultiTheme(Website):

    @route()
    def theme_customize_get(self, xml_ids):
        """Override, because original method return view.xml_id,
        which are 'website_multi_theme.auto_view_ID_WEBSITE',
        while client works with original IDs.
        """
        enable = []
        disable = []
        ids = self.get_view_ids(xml_ids)
        ir_ui_view = request.env['ir.ui.view'].with_context(active_test=True)
        for view in ir_ui_view.browse(ids):
            if view.active:
                enable.append(view.key)
            else:
                disable.append(view.key)
        return [enable, disable]
