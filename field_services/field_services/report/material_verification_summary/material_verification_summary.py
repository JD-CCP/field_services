# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": "Project", "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 180},
		{"label": "Team", "fieldname": "service_team", "fieldtype": "Link", "options": "Service Team", "width": 150},
		{"label": "Issued Value", "fieldname": "issued_value", "fieldtype": "Currency", "width": 130},
		{"label": "Consumed Value", "fieldname": "consumed_value", "fieldtype": "Currency", "width": 140},
		{"label": "Returned Value", "fieldname": "returned_value", "fieldtype": "Currency", "width": 140},
		{"label": "Deviation Value", "fieldname": "deviation_value", "fieldtype": "Currency", "width": 140},
		{"label": "Deviation %", "fieldname": "deviation_pct", "fieldtype": "Percent", "width": 110},
	]


def get_data(filters):
	conditions = "mv.docstatus = 1"
	params = {}

	if filters.get("from_date"):
		conditions += " AND mv.verification_date >= %(from_date)s"
		params["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions += " AND mv.verification_date <= %(to_date)s"
		params["to_date"] = filters.to_date
	if filters.get("service_region"):
		conditions += " AND p.service_region = %(service_region)s"
		params["service_region"] = filters.service_region
	if filters.get("deviation_type"):
		conditions += (
			" AND EXISTS (SELECT 1 FROM `tabVerification Item` vi "
			"WHERE vi.parent = mv.name AND vi.deviation_type = %(deviation_type)s)"
		)
		params["deviation_type"] = filters.deviation_type

	rows = frappe.db.sql(
		f"""
		SELECT mv.project, mv.service_team,
		       mv.total_issued_cost, mv.total_consumed_cost,
		       mv.total_returned_cost, mv.total_deviation_cost
		FROM `tabMaterial Verification` mv
		LEFT JOIN `tabProject` p ON p.name = mv.project
		WHERE {conditions}
		ORDER BY mv.total_deviation_cost DESC
		""",
		params,
		as_dict=True,
	)

	data = []
	for r in rows:
		issued = flt(r.total_issued_cost)
		deviation = flt(r.total_deviation_cost)
		data.append({
			"project": r.project,
			"service_team": r.service_team,
			"issued_value": issued,
			"consumed_value": flt(r.total_consumed_cost),
			"returned_value": flt(r.total_returned_cost),
			"deviation_value": deviation,
			"deviation_pct": (deviation / issued * 100) if issued else 0,
		})
	return data
