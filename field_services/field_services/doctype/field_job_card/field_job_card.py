import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class FieldJobCard(Document):
	def validate(self):
		self.set_sign_off_date()

	def set_sign_off_date(self):
		if (self.sign_off_name or self.client_signature) and not self.sign_off_date:
			self.sign_off_date = now_datetime()
		elif not self.sign_off_name and not self.client_signature:
			self.sign_off_date = None
