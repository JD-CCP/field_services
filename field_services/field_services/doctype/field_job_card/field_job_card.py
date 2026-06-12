import frappe
from frappe.model.document import Document
from frappe.model.naming import getseries
from frappe.utils import now_datetime


class FieldJobCard(Document):
	def autoname(self):
		if not self.project:
			frappe.throw("Project is required to create a Field Job Card")
		date_part = now_datetime().strftime("%y%m%d")
		series_key = f"FJC-{self.project}-{date_part}"
		counter = getseries(series_key, 1)
		self.name = f"{self.project}-{date_part}-{counter}"
