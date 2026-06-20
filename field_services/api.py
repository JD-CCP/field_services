import frappe
import requests
from frappe.utils import flt, now_datetime, time_diff_in_hours
from frappe.utils.password import get_decrypted_password

# Whitelisted methods for Field Services portals

SLOTS = ["Slot 1", "Slot 2", "Slot 3"]
LOCKED_BOOKING_STATUSES = ("Pre-Scheduled", "Confirmed", "Dispatched")


def _booking_card(b):
	start = b.get("site_start_time")
	end = b.get("site_end_time")
	time_range = ""
	if start and end:
		time_range = f"{frappe.utils.format_datetime(start, 'HH:mm')}-{frappe.utils.format_datetime(end, 'HH:mm')}"
	return {
		"name": b.get("name"),
		"project": b.get("project"),
		"project_name": b.get("project_name") or b.get("project"),
		"customer": b.get("customer"),
		"site_area": b.get("site_area"),
		"project_type": b.get("project_type"),
		"scheduling_priority": b.get("scheduling_priority"),
		"work_type": b.get("work_type"),
		"schedule_status": b.get("schedule_status"),
		"time_range": time_range,
		"readiness_status": b.get("readiness_status"),
		"double_booking_status": b.get("double_booking_status"),
		"alert_message": b.get("alert_message"),
	}


def _scheduled_day_map(teams):
	"""For each team -> list of (repeat_days set, start_date, end_date) from
	its active Team Schedules, to tell if a team works a given day."""
	out = {}
	for t in teams:
		scheds = frappe.get_all(
			"Team Schedule",
			filters={"service_team": t["name"], "status": "Active"},
			fields=["name", "start_date", "end_date"],
		)
		entries = []
		for s in scheds:
			days = set(frappe.get_all("Schedule Day", filters={"parent": s.name, "parenttype": "Team Schedule"}, pluck="day"))
			entries.append((days, frappe.utils.getdate(s.start_date), frappe.utils.getdate(s.end_date) if s.end_date else None))
		out[t["name"]] = entries
	return out


def _team_works_day(entries, day):
	weekday = day.strftime("%A")
	for days, s_start, s_end in entries:
		if day < s_start:
			continue
		if s_end and day > s_end:
			continue
		if weekday in days:
			return True
	return False


@frappe.whitelist()
def get_dispatch_data(view, date, region=None):
	"""Dispatch board data for Today / Week / Month views."""
	from frappe.utils import add_days, getdate

	view = (view or "Today").title()
	anchor = getdate(date)

	team_filters = {}
	if region:
		team_filters["service_region"] = region
	teams = frappe.get_all(
		"Service Team", filters=team_filters,
		fields=["name", "team_name", "service_region"], order_by="team_name",
	)
	team_names = [t["name"] for t in teams]

	bfields = ["name", "project", "customer", "site_area", "project_type",
			   "scheduling_priority", "service_team", "schedule_date", "slot",
			   "work_type", "schedule_status", "site_start_time", "site_end_time",
			   "readiness_status", "double_booking_status", "alert_message"]

	def load_bookings(start, end):
		if not team_names:
			return []
		rows = frappe.get_all(
			"Field Service Booking",
			filters={"service_team": ["in", team_names], "schedule_date": ["between", [start, end]],
					 "schedule_status": ["!=", "Cancelled"]},
			fields=bfields,
		)
		pc = {}
		for r in rows:
			if r.project and r.project not in pc:
				pc[r.project] = frappe.db.get_value("Project", r.project, "project_name")
			r["project_name"] = pc.get(r.project)
		return rows

	if view == "Today":
		return _today_view(teams, anchor, load_bookings(anchor, anchor))
	if view == "Week":
		start = add_days(anchor, -anchor.weekday())  # Monday
		days = [add_days(start, i) for i in range(7)]
		return _week_view(teams, days, load_bookings(days[0], days[-1]))
	# Month
	start = anchor.replace(day=1)
	next_month = (start.replace(day=28) + __import__("datetime").timedelta(days=4)).replace(day=1)
	end = next_month - __import__("datetime").timedelta(days=1)
	days = [add_days(start, i) for i in range((end - start).days + 1)]
	return _month_view(teams, days, load_bookings(start, end))


def _today_view(teams, day, bookings):
	by_team = {}
	for b in bookings:
		by_team.setdefault(b["service_team"], []).append(b)
	rows = []
	for t in teams:
		tb = by_team.get(t["name"], [])
		slots = {s: None for s in SLOTS}
		unslotted = []
		alerts = set()
		for b in tb:
			card = _booking_card(b)
			if b.get("slot") in slots and slots[b["slot"]] is None:
				slots[b["slot"]] = card
			else:
				unslotted.append(card)
			if b.get("readiness_status") == "Not Ready" and b.get("alert_message"):
				alerts.add(b["alert_message"])
			if b.get("double_booking_status") in ("Warning", "Clash"):
				alerts.add("Possible double booking")
		rows.append({
			"name": t["name"], "team_name": t["team_name"], "region": t["service_region"],
			"slots": slots, "unslotted": unslotted, "alerts": sorted(alerts),
		})
	return {"view": "Today", "date": str(day), "teams": rows}


def _week_view(teams, days, bookings):
	by = {}
	for b in bookings:
		by.setdefault((b["service_team"], str(b["schedule_date"])), []).append(b)
	rows = []
	for t in teams:
		cells = []
		for d in days:
			tb = by.get((t["name"], str(d)), [])
			booked = len(tb)
			tentative = sum(1 for b in tb if b["schedule_status"] == "Tentative")
			cells.append({
				"date": str(d), "booked": booked, "free": max(0, 3 - booked),
				"tentative": tentative,
				"statuses": [b["schedule_status"] for b in tb],
			})
		rows.append({"name": t["name"], "team_name": t["team_name"], "days": cells})
	return {"view": "Week", "days": [str(d) for d in days], "teams": rows}


def _month_view(teams, days, bookings):
	sched = _scheduled_day_map(teams)
	by_day = {}
	for b in bookings:
		by_day.setdefault(str(b["schedule_date"]), []).append(b)
	total_slots_per_day = len(teams) * 3
	cells = []
	for d in days:
		db = by_day.get(str(d), [])
		booked = len(db)
		unavailable = sum(0 if _team_works_day(sched.get(t["name"], []), d) else 1 for t in teams)
		cells.append({
			"date": str(d), "day_num": d.day,
			"total_slots": total_slots_per_day, "booked": booked,
			"available": max(0, total_slots_per_day - booked),
			"p1p2": sum(1 for b in db if (b.get("scheduling_priority") or 5) <= 2),
			"tentative": sum(1 for b in db if b["schedule_status"] == "Tentative"),
			"confirmed": sum(1 for b in db if b["schedule_status"] == "Confirmed"),
			"blocked": sum(1 for b in db if b.get("double_booking_status") in ("Warning", "Clash") or b.get("readiness_status") == "Not Ready"),
			"teams_unavailable": unavailable,
		})
	return {"view": "Month", "days": cells}


@frappe.whitelist()
def get_calendar_data(start_date, end_date, region=None):
	"""Feed the Field Services calendar: teams (with availability for the
	period) and their Project Bookings overlapping the visible range."""
	from field_services.field_services.doctype.team_schedule.team_schedule import (
		get_available_hours,
		get_booked_hours,
	)

	team_filters = {}
	if region:
		team_filters["service_region"] = region
	teams = frappe.get_all(
		"Service Team",
		filters=team_filters,
		fields=["name", "team_name", "service_region"],
		order_by="team_name",
	)

	team_rows = []
	for t in teams:
		total = get_available_hours(t.name, start_date, end_date)["total_hours"]
		booked = get_booked_hours(t.name, start_date, end_date)
		team_rows.append({
			"name": t.name,
			"team_name": t.team_name,
			"region": t.service_region,
			"total_hours": total,
			"booked_hours": booked,
			"available_hours": total - booked,
		})

	bookings = []
	if teams:
		rows = frappe.get_all(
			"Project Booking",
			filters={
				"service_team": ["in", [t.name for t in teams]],
				"status": ["!=", "Cancelled"],
				"booking_start": ["<=", f"{end_date} 23:59:59"],
				"booking_end": [">=", f"{start_date} 00:00:00"],
			},
			fields=[
				"name", "project", "service_team", "booking_start", "booking_end",
				"booked_hours", "status",
			],
		)
		proj_cache = {}
		for b in rows:
			if b.project not in proj_cache:
				proj_cache[b.project] = frappe.db.get_value(
					"Project", b.project, ["project_name", "customer"], as_dict=True
				) or frappe._dict()
			p = proj_cache[b.project]
			b["project_name"] = p.get("project_name") or b.project
			b["customer"] = p.get("customer")
			bookings.append(b)

	return {"teams": team_rows, "bookings": bookings}


@frappe.whitelist()
def confirm_stock_receipt(stock_entry, pin):
	"""Team lead confirms receipt of stock transfer."""
	se = frappe.get_doc("Stock Entry", stock_entry)
	if se.confirmation_status != "Pending Confirmation":
		frappe.throw("This transfer is not pending confirmation")

	# Get the employee for the current user
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw("No Employee record for current user")

	# Verify PIN (Password field must be decrypted, not read via db.get_value)
	stored_pin = get_decrypted_password("Employee", employee, "confirmation_pin", raise_exception=False)
	if not stored_pin or str(pin) != str(stored_pin):
		frappe.throw("Invalid PIN")

	# Confirm
	se.db_set("confirmation_status", "Confirmed")
	se.db_set("confirmed_by", employee)
	se.db_set("confirmed_on", now_datetime())
	se.add_comment("Info", f"Receipt confirmed by {employee}")
	return {"status": "Confirmed"}


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
