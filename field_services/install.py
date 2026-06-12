import frappe


def after_migrate():
	ensure_project_site_field()
	ensure_project_field_job_card_link()


def ensure_project_site_field():
	"""Add a 'site' Link field to Project so Field Job Card can fetch it."""
	if not frappe.db.exists("DocType", "Site"):
		return
	if frappe.db.exists("Custom Field", {"dt": "Project", "fieldname": "site"}):
		return

	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": "Project",
		"fieldname": "site",
		"label": "Site",
		"fieldtype": "Link",
		"options": "Site",
		"insert_after": "project_name",
	}).insert(ignore_permissions=True)


def ensure_project_field_job_card_link():
	"""Add Field Job Card to Project's Connections section (idempotent)."""
	if not frappe.db.exists("DocType", "Field Job Card"):
		return

	project = frappe.get_doc("DocType", "Project")
	if any(l.link_doctype == "Field Job Card" for l in project.links or []):
		return

	project.append("links", {
		"link_doctype": "Field Job Card",
		"link_fieldname": "project",
		"group": "Project",
		"custom": 1,
	})
	project.flags.ignore_permissions = True
	project.save()
