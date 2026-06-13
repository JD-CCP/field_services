import frappe
import requests
from frappe.utils import flt, now_datetime, time_diff_in_hours

# Whitelisted methods for Field Services portals


@frappe.whitelist()
def explode_service_bom(service_bom, qty):
	"""Returns exploded item list for a Service BOM x quantity."""
	qty = flt(qty)
	bom = frappe.get_doc("Service BOM", service_bom)
	items = []
	for item in bom.items:
		if not item.is_optional:
			items.append({
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.effective_qty * qty,
				"uom": item.uom,
				"rate": item.rate,
			})
	return items


NOMINATIM_HEADERS = {
	"User-Agent": "FieldServices/1.0 (Frappe App - CompuCable Projects)"
}


@frappe.whitelist()
def search_address(query):
	"""Search for address suggestions using OpenStreetMap Nominatim.

	Returns a list of suggestion dicts with parsed address components.
	"""
	if not query or len(query) < 3:
		return []

	try:
		response = requests.get(
			"https://nominatim.openstreetmap.org/search",
			params={
				"q": query,
				"format": "json",
				"addressdetails": 1,
				"limit": 5,
			},
			headers=NOMINATIM_HEADERS,
			timeout=10,
		)
		response.raise_for_status()
		results = response.json()
	except Exception as e:
		frappe.log_error(f"Address search failed: {e}", "Nominatim Search")
		return []

	suggestions = []
	for r in results:
		addr = r.get("address", {})
		line1_parts = [addr.get("house_number"), addr.get("road")]
		line1 = " ".join(p for p in line1_parts if p)
		line2 = addr.get("suburb") or addr.get("neighbourhood") or addr.get("hamlet") or ""
		city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or ""

		suggestions.append(
			{
				"display_name": r.get("display_name"),
				"lat": float(r.get("lat")) if r.get("lat") else None,
				"lng": float(r.get("lon")) if r.get("lon") else None,
				"address_line1": line1,
				"address_line2": line2,
				"city": city,
				"state": addr.get("state") or "",
				"pincode": addr.get("postcode") or "",
				"country": addr.get("country") or "",
			}
		)

	return suggestions


@frappe.whitelist()
def geocode_address(address):
	"""Geocode an address string using OpenStreetMap Nominatim.

	Returns a dict with lat/lng/display_name or None if not found.
	"""
	if not address:
		return None

	try:
		response = requests.get(
			"https://nominatim.openstreetmap.org/search",
			params={
				"q": address,
				"format": "json",
				"limit": 1,
			},
			headers=NOMINATIM_HEADERS,
			timeout=10,
		)
		response.raise_for_status()
		results = response.json()
		if results:
			return {
				"lat": float(results[0]["lat"]),
				"lng": float(results[0]["lon"]),
				"display_name": results[0].get("display_name"),
			}
	except Exception as e:
		frappe.log_error(f"Geocoding failed: {e}", "Nominatim Geocode")

	return None


@frappe.whitelist()
def clock_in(job_card):
	"""Start or resume timing on a job card."""
	doc = frappe.get_doc("Field Job Card", job_card)
	if doc.status == "Completed":
		frappe.throw("Cannot clock in on a completed Job Card")

	row = doc.append("time_logs", {
		"from_time": now_datetime(),
		"activity_type": "",  # can be set later
	})
	doc.status = "Work In Progress"
	if not doc.started_at:
		doc.started_at = now_datetime()
	doc.save(ignore_permissions=True)
	return {"time_log": row.name, "from_time": str(row.from_time)}


@frappe.whitelist()
def pause_job(job_card):
	"""Pause the current time log."""
	doc = frappe.get_doc("Field Job Card", job_card)
	close_active_time_log(doc)
	doc.status = "Paused"
	doc.save(ignore_permissions=True)
	return {"status": "Paused"}


@frappe.whitelist()
def resume_job(job_card):
	"""Resume after pause - same as clock_in."""
	return clock_in(job_card)


@frappe.whitelist()
def clock_out(job_card):
	"""Stop timing, calculate totals, create Timesheet entry."""
	doc = frappe.get_doc("Field Job Card", job_card)
	close_active_time_log(doc)

	doc.actual_hours = sum(r.hours or 0 for r in doc.time_logs)
	doc.completed_at = now_datetime()
	doc.status = "Completed"
	create_timesheet_entry(doc)
	doc.save(ignore_permissions=True)
	return {"status": "Completed", "actual_hours": doc.actual_hours}


def close_active_time_log(doc):
	"""Set to_time/hours on the latest open time log row, if any."""
	for row in reversed(doc.time_logs):
		if row.from_time and not row.to_time:
			row.to_time = now_datetime()
			row.hours = time_diff_in_hours(row.to_time, row.from_time)
			break


@frappe.whitelist()
def load_project_materials(job_card):
	"""Populate Job Card Material Used from team store stock for this project."""
	doc = frappe.get_doc("Field Job Card", job_card)

	# The team is assigned at project level; fall back to the job card's
	# own team if the project does not have one set.
	team_name = frappe.db.get_value("Project", doc.project, "service_team") or doc.service_team
	if not team_name:
		frappe.throw("No Service Team assigned to this Project")
	team_warehouse = frappe.db.get_value("Service Team", team_name, "team_warehouse")
	if not team_warehouse:
		frappe.throw("Service Team has no warehouse")

	# All items transferred into the team store for this project
	items = frappe.db.sql(
		"""
		SELECT sed.item_code, sed.item_name, SUM(sed.qty) AS total_qty,
		       sed.uom
		FROM `tabStock Entry Detail` sed
		JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1
		  AND se.stock_entry_type = 'Material Transfer'
		  AND sed.t_warehouse = %s
		  AND se.project = %s
		GROUP BY sed.item_code, sed.item_name, sed.uom
		""",
		(team_warehouse, doc.project),
		as_dict=True,
	)

	# Clear existing material rows and repopulate
	doc.set("materials_used", [])
	for item in items:
		doc.append("materials_used", {
			"item_code": item.item_code,
			"item_name": item.item_name,
			"issued_qty": item.total_qty,
			"qty_used": 0,
			"uom": item.uom,
		})
	doc.save(ignore_permissions=True)
	return {"items_loaded": len(items)}


def get_job_card_employees(job_card_doc):
	"""Employees who get timesheet entries: the members listed on the job
	card's own team table (anyone removed there is skipped)."""
	employees = []
	for member in job_card_doc.team_members or []:
		if member.employee not in employees:
			employees.append(member.employee)
	if not employees:
		frappe.throw("No team members listed on this Job Card - add at least one before clocking out")
	return employees


def create_timesheet_entry(job_card_doc):
	"""Create or append to a draft Timesheet for the job card employee
	and every active member of the linked service team."""
	first_log = job_card_doc.time_logs[0] if job_card_doc.time_logs else None
	last_log = job_card_doc.time_logs[-1] if job_card_doc.time_logs else None
	if not first_log:
		return

	default_activity = None
	if frappe.get_meta("Projects Settings").has_field("default_activity_type"):
		default_activity = frappe.db.get_single_value("Projects Settings", "default_activity_type")

	ts_data = {
		"activity_type": first_log.activity_type or default_activity or "Execution",
		"from_time": first_log.from_time,
		"to_time": last_log.to_time or now_datetime(),
		"hours": job_card_doc.actual_hours,
		"project": job_card_doc.project,
		"field_job_card": job_card_doc.name,
	}

	employees = get_job_card_employees(job_card_doc)
	for employee in employees:
		existing = frappe.db.get_value(
			"Timesheet",
			{"employee": employee, "docstatus": 0},
			"name",
		)

		if existing:
			ts = frappe.get_doc("Timesheet", existing)
			row = ts.append("time_logs", ts_data)
			ts.save(ignore_permissions=True)
		else:
			ts = frappe.get_doc({
				"doctype": "Timesheet",
				"employee": employee,
				"time_logs": [ts_data],
			})
			ts.insert(ignore_permissions=True)
			row = ts.time_logs[0]

		# The job card keeps a direct reference to the first listed
		# member's entry (normally the team lead)
		if employee == employees[0]:
			job_card_doc.timesheet = ts.name
			job_card_doc.timesheet_detail = row.name
