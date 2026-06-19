# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe


def on_submit(doc, method=None):
	"""When a Material Transfer lands stock in a Service Team's store,
	flag it for the team lead to confirm receipt."""
	target_warehouses = {row.t_warehouse for row in doc.items if row.t_warehouse}
	if not target_warehouses:
		return

	teams = frappe.get_all(
		"Service Team",
		filters={"team_warehouse": ["in", list(target_warehouses)]},
		fields=["name", "team_name", "team_lead", "team_warehouse"],
	)
	if not teams:
		return

	doc.db_set("confirmation_status", "Pending Confirmation")
	for team in teams:
		notify_team_lead(doc, team)


def notify_team_lead(doc, team):
	"""Send an in-app notification to the team lead to confirm receipt."""
	if not team.get("team_lead"):
		return
	user = frappe.db.get_value("Employee", team.team_lead, "user_id")
	if not user:
		return

	frappe.get_doc({
		"doctype": "Notification Log",
		"subject": frappe._("Stock receipt to confirm: {0}").format(doc.name),
		"email_content": frappe._(
			"A stock transfer to {0} ({1}) is pending your confirmation of receipt."
		).format(team.get("team_name") or team.get("name"), team.get("team_warehouse")),
		"for_user": user,
		"type": "Alert",
		"document_type": "Stock Entry",
		"document_name": doc.name,
		"from_user": frappe.session.user,
	}).insert(ignore_permissions=True)
