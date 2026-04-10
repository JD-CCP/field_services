# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Site(Document):
	def autoname(self):
		if self.site_code:
			self.name = f"SITE-{self.site_code}"
		else:
			self.name = self.site_name
