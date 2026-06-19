# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate


class TeamSchedule(Document):
	def validate(self):
		if self.end_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw("End Date cannot be before Start Date")


@frappe.whitelist()
def get_available_hours(team, start_date, end_date):
	"""Sum scheduled shift hours for a team across a date range, based on
	its active Team Schedules and their repeat-on weekdays."""
	start = getdate(start_date)
	end = getdate(end_date)

	schedules = frappe.get_all(
		"Team Schedule",
		filters={"service_team": team, "status": "Active"},
		fields=["name", "shift_type", "start_date", "end_date"],
	)

	# preload repeat days per schedule and shift info
	days_map = {}
	for s in schedules:
		days_map[s.name] = set(
			frappe.get_all("Schedule Day", filters={"parent": s.name, "parenttype": "Team Schedule"}, pluck="day")
		)

	shift_cache = {}

	def shift_info(shift_type):
		if shift_type not in shift_cache:
			shift_cache[shift_type] = frappe.db.get_value(
				"FS Shift Type", shift_type, ["hours", "is_on_call"], as_dict=True
			) or frappe._dict(hours=0, is_on_call=0)
		return shift_cache[shift_type]

	total_hours = 0.0
	on_call_hours = 0.0

	day = start
	while day <= end:
		weekday = day.strftime("%A")  # Monday .. Sunday
		for s in schedules:
			if day < getdate(s.start_date):
				continue
			if s.end_date and day > getdate(s.end_date):
				continue
			if weekday in days_map.get(s.name, ()):
				info = shift_info(s.shift_type)
				total_hours += flt(info.hours)
				if info.is_on_call:
					on_call_hours += flt(info.hours)
		day = add_days(day, 1)

	return {"total_hours": total_hours, "on_call_hours": on_call_hours}


@frappe.whitelist()
def get_booked_hours(team, start_date, end_date):
	"""Sum booked hours from Project Bookings for a team whose booking
	start date falls within the given range (Cancelled excluded)."""
	meta = frappe.get_meta("Project Booking")
	if not (meta.has_field("service_team") and meta.has_field("booked_hours")):
		return 0.0

	conditions = "service_team = %(team)s AND status != 'Cancelled'"
	params = {"team": team}
	if meta.has_field("booking_start"):
		conditions += " AND DATE(booking_start) BETWEEN %(start_date)s AND %(end_date)s"
		params["start_date"] = getdate(start_date)
		params["end_date"] = getdate(end_date)

	total = frappe.db.sql(
		f"SELECT SUM(booked_hours) FROM `tabProject Booking` WHERE {conditions}", params
	)
	return flt(total[0][0]) if total else 0.0
