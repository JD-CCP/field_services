# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import flt, now_datetime


class MaterialVerification(Document):
	def autoname(self):
		if not self.project:
			frappe.throw("Project is required to name a Material Verification")
		self.name = make_autoname(f"{self.project}-MV-.#####")

	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		total_issued = total_consumed = total_returned = total_deviation = 0
		for it in self.items:
			it.deviation_qty = flt(it.issued_qty) - flt(it.declared_used_qty) - flt(it.returned_qty)
			it.deviation_cost = flt(it.deviation_qty) * flt(it.rate)
			total_issued += flt(it.issued_qty) * flt(it.rate)
			total_consumed += flt(it.declared_used_qty) * flt(it.rate)
			total_returned += flt(it.returned_qty) * flt(it.rate)
			total_deviation += flt(it.deviation_cost)

		self.total_issued_cost = total_issued
		self.total_consumed_cost = total_consumed
		self.total_returned_cost = total_returned
		self.total_deviation_cost = total_deviation

	def before_submit(self):
		# Every unexplained (positive) deviation must be categorised before
		# the verification can be submitted and stock written off.
		for it in self.items:
			if flt(it.deviation_qty) > 0 and (it.deviation_type or "N/A") == "N/A":
				frappe.throw(
					f"Row #{it.idx} ({it.item_code}): a positive deviation of "
					f"{it.deviation_qty} requires a Deviation Type before submitting."
				)

	# ------------------------------------------------------------------ #
	# Populate
	# ------------------------------------------------------------------ #
	@frappe.whitelist()
	def populate_from_project(self):
		"""Pull issued qty (team-store transfers) and declared used qty
		(Field Job Card materials) for this project, grouped by item."""
		team = self.service_team or frappe.db.get_value("Project", self.project, "service_team")
		if not team:
			frappe.throw("No Service Team assigned to this Project")
		team_wh = frappe.db.get_value("Service Team", team, "team_warehouse")
		if not team_wh:
			frappe.throw("Service Team has no warehouse")
		self.service_team = team

		issued = frappe.db.sql(
			"""
			SELECT sed.item_code, SUM(sed.qty) AS qty, sed.valuation_rate
			FROM `tabStock Entry Detail` sed
			JOIN `tabStock Entry` se ON se.name = sed.parent
			WHERE se.docstatus = 1
			  AND se.stock_entry_type = 'Material Transfer'
			  AND sed.t_warehouse = %s
			  AND se.project = %s
			GROUP BY sed.item_code, sed.valuation_rate
			""",
			(team_wh, self.project),
			as_dict=True,
		)
		issued_map = {r.item_code: r for r in issued}

		used = frappe.db.sql(
			"""
			SELECT mu.item_code, SUM(mu.qty_used) AS qty
			FROM `tabJob Card Material Used` mu
			JOIN `tabField Job Card` jc ON jc.name = mu.parent
			WHERE jc.project = %s
			GROUP BY mu.item_code
			""",
			(self.project,),
			as_dict=True,
		)
		used_map = {r.item_code: flt(r.qty) for r in used}

		def rate_for(item_code, fallback):
			return flt(fallback) or flt(frappe.db.get_value("Item", item_code, "valuation_rate"))

		self.set("items", [])
		for item_code, r in issued_map.items():
			self.append("items", {
				"item_code": item_code,
				"issued_qty": flt(r.qty),
				"declared_used_qty": used_map.get(item_code, 0),
				"rate": rate_for(item_code, r.valuation_rate),
				"deviation_type": "N/A",
			})
		# items declared used but never issued to the store
		for item_code, qty in used_map.items():
			if item_code not in issued_map:
				self.append("items", {
					"item_code": item_code,
					"issued_qty": 0,
					"declared_used_qty": qty,
					"rate": rate_for(item_code, 0),
					"deviation_type": "N/A",
				})

		self.save()
		return {"item_count": len(self.items)}

	# ------------------------------------------------------------------ #
	# Submit -> stock movements
	# ------------------------------------------------------------------ #
	def on_submit(self):
		team = self.service_team or frappe.db.get_value("Project", self.project, "service_team")
		team_wh = frappe.db.get_value("Service Team", team, "team_warehouse")
		if not team_wh:
			frappe.throw("Service Team has no warehouse")
		return_wh = self.return_warehouse or frappe.db.get_value("Service Team", team, "source_warehouse")
		company = (
			frappe.db.get_value("Project", self.project, "company")
			or frappe.defaults.get_defaults().get("company")
		)

		created = []

		# a) consumed -> Material Issue
		consumed = [(it.item_code, it.declared_used_qty) for it in self.items if flt(it.declared_used_qty) > 0]
		if consumed:
			created.append(self._make_stock_entry("Material Issue", company, team_wh, None, consumed))

		# b) returns -> Material Transfer to return warehouse
		returns = [(it.item_code, it.returned_qty) for it in self.items if flt(it.returned_qty) > 0]
		if returns:
			if not return_wh:
				frappe.throw("A Return Warehouse is required when there are returned items")
			created.append(self._make_stock_entry("Material Transfer", company, team_wh, return_wh, returns))

		# c) deviations (Lost/Damaged) -> Material Issue write-off
		write_offs = [
			(it.item_code, it.deviation_qty)
			for it in self.items
			if flt(it.deviation_qty) > 0 and it.deviation_type in ("Lost", "Damaged")
		]
		if write_offs:
			created.append(self._make_stock_entry("Material Issue", company, team_wh, None, write_offs))

		# update project actual material cost + verification stamp
		actual_cost = flt(self.total_consumed_cost) + flt(self.total_deviation_cost)
		if frappe.get_meta("Project").has_field("total_actual_material_cost"):
			frappe.db.set_value("Project", self.project, "total_actual_material_cost", actual_cost)
		frappe.db.set_value("Project", self.project, {
			"material_verified_by": self.verified_by,
			"material_verified_on": now_datetime(),
		})

		self.db_set("status", "Submitted")
		if created:
			self.add_comment("Info", "Created stock entries: " + ", ".join(created))

	def _make_stock_entry(self, purpose, company, source, target, rows):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = purpose
		se.company = company
		se.project = self.project
		for item_code, qty in rows:
			if not flt(qty):
				continue
			row = {"item_code": item_code, "qty": flt(qty)}
			if source:
				row["s_warehouse"] = source
			if target:
				row["t_warehouse"] = target
			se.append("items", row)
		se.insert(ignore_permissions=True)
		se.submit()
		return se.name

	def on_cancel(self):
		self.db_set("status", "Draft")

	# ------------------------------------------------------------------ #
	# PM approval
	# ------------------------------------------------------------------ #
	@frappe.whitelist()
	def pm_approve(self, employee=None, notes=None):
		employee = employee or frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		self.db_set("pm_approved_by", employee)
		self.db_set("pm_approved_on", now_datetime())
		if notes:
			self.db_set("pm_notes", notes)
		self.db_set("status", "PM Approved")
		self.add_comment("Workflow", f"PM Approved by {employee or frappe.session.user}")
		return {"status": "PM Approved"}

	@frappe.whitelist()
	def pm_reject(self, employee=None, notes=None):
		employee = employee or frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if notes:
			self.db_set("pm_notes", notes)
		self.db_set("status", "PM Rejected")
		self.add_comment("Workflow", f"PM Rejected by {employee or frappe.session.user}")
		return {"status": "PM Rejected"}
