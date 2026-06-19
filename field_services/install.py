import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
	ensure_custom_fields()


CUSTOM_FIELDS = {
	"Project": [
		{
			"fieldname": "site",
			"label": "Site",
			"fieldtype": "Link",
			"options": "Site",
			"insert_after": "project_name",
		},
		{
			"fieldname": "service_team",
			"label": "Service Team",
			"fieldtype": "Link",
			"options": "Service Team",
			"insert_after": "site",
		},
		{
			"fieldname": "service_region",
			"label": "Service Region",
			"fieldtype": "Link",
			"options": "Service Region",
			"insert_after": "service_team",
		},
		{
			"fieldname": "project_booking",
			"label": "Project Booking",
			"fieldtype": "Link",
			"options": "Project Booking",
			"insert_after": "service_region",
		},
		{
			"fieldname": "material_verified_by",
			"label": "Material Verified By",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "project_booking",
		},
		{
			"fieldname": "material_verified_on",
			"label": "Material Verified On",
			"fieldtype": "Datetime",
			"insert_after": "material_verified_by",
		},
		{
			"fieldname": "hours_verified_by",
			"label": "Hours Verified By",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "material_verified_on",
		},
		{
			"fieldname": "hours_verified_on",
			"label": "Hours Verified On",
			"fieldtype": "Datetime",
			"insert_after": "hours_verified_by",
		},
		{
			"fieldname": "verification_notes",
			"label": "Verification Notes",
			"fieldtype": "Text Editor",
			"insert_after": "hours_verified_on",
		},
		{
			"fieldname": "total_planned_material_cost",
			"label": "Total Planned Material Cost",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "verification_notes",
		},
		{
			"fieldname": "total_actual_material_cost",
			"label": "Total Actual Material Cost",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_planned_material_cost",
		},
	],
	"Quotation": [
		{
			"fieldname": "project",
			"label": "Project",
			"fieldtype": "Link",
			"options": "Project",
			"insert_after": "order_type",
		},
		{
			"fieldname": "site",
			"label": "Site",
			"fieldtype": "Link",
			"options": "Site",
			"insert_after": "project",
		},
	],
	"Stock Entry": [
		{
			"fieldname": "confirmation_status",
			"label": "Confirmation Status",
			"fieldtype": "Select",
			"options": "\nPending Confirmation\nConfirmed\nDiscrepancy",
			"insert_after": "purpose",
			"allow_on_submit": 1,
			"read_only": 1,
		},
		{
			"fieldname": "confirmed_by",
			"label": "Confirmed By",
			"fieldtype": "Link",
			"options": "Employee",
			"read_only": 1,
			"depends_on": "confirmation_status",
			"insert_after": "confirmation_status",
			"allow_on_submit": 1,
		},
		{
			"fieldname": "confirmed_on",
			"label": "Confirmed On",
			"fieldtype": "Datetime",
			"read_only": 1,
			"insert_after": "confirmed_by",
			"allow_on_submit": 1,
		},
	],
	"Warehouse": [
		{
			"fieldname": "is_field_service_store",
			"label": "Field Service Store",
			"fieldtype": "Check",
			"description": "Mark this warehouse as a Field Services team store so it can be selected as a team's warehouse.",
			"insert_after": "warehouse_name",
		},
	],
	"Employee": [
		{
			"fieldname": "confirmation_pin",
			"label": "Confirmation PIN",
			"fieldtype": "Password",
			"description": "4-6 digit PIN used to confirm stock receipts",
			"insert_after": "personal_email",
		},
	],
	"Timesheet Detail": [
		{
			"fieldname": "field_job_card",
			"label": "Field Job Card",
			"fieldtype": "Link",
			"options": "Field Job Card",
			"read_only": 1,
			"insert_after": "project",
		},
	],
}


def ensure_custom_fields():
	"""Create/update all Field Services custom fields, tagging each with the
	Field Services module so they export cleanly as fixtures."""
	for fields in CUSTOM_FIELDS.values():
		for df in fields:
			df.setdefault("module", "Field Services")

	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
