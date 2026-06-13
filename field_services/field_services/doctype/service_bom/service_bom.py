# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ServiceBOM(Document):
	def validate(self):
		if not self.items:
			frappe.throw("At least one BOM Item is required")
		self.calculate_totals()

	def calculate_totals(self):
		total_cost = 0
		total_minutes = 0
		for item in self.items:
			item.effective_qty = item.qty_per_unit * (1 + (item.wastage_percent or 0) / 100)
			item.amount = item.effective_qty * (item.rate or 0)
			total_cost += item.amount
		for op in self.operations:
			total_minutes += (op.time_per_unit or 0)
		self.total_material_cost = total_cost
		self.total_labour_minutes = total_minutes
		self.estimated_cost_per_unit = total_cost  # labour costing added later
