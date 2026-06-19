# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import add_days, add_to_date, flt, get_datetime, getdate, time_diff_in_hours


class ProjectBooking(Document):
	def autoname(self):
		if not self.project:
			frappe.throw("Project is required to name a Project Booking")
		self.name = make_autoname(f"{self.project}-B.#####")

	def validate(self):
		self.calculate_booked_hours()
		self.check_overlap()

	def calculate_booked_hours(self):
		if self.booking_start and self.booking_end:
			if get_datetime(self.booking_end) <= get_datetime(self.booking_start):
				frappe.throw("Booking End must be after Booking Start")
			self.booked_hours = time_diff_in_hours(self.booking_end, self.booking_start)
		else:
			self.booked_hours = 0

	def check_overlap(self):
		"""A team cannot be double-booked unless an override reason is given."""
		clashes = frappe.db.sql(
			"""
			SELECT name, booking_start, booking_end
			FROM `tabProject Booking`
			WHERE service_team = %(team)s
			  AND name != %(name)s
			  AND status != 'Cancelled'
			  AND booking_start < %(end)s
			  AND booking_end > %(start)s
			""",
			{
				"team": self.service_team,
				"name": self.name or "new",
				"start": self.booking_start,
				"end": self.booking_end,
			},
			as_dict=True,
		)
		if clashes and not self.override_reason:
			names = ", ".join(c.name for c in clashes)
			frappe.throw(
				f"This booking overlaps existing booking(s) for {self.service_team}: {names}. "
				"Provide an Override Reason to proceed."
			)


# ---------------------------------------------------------------------- #
# API
# ---------------------------------------------------------------------- #
@frappe.whitelist()
def get_booking_suggestions(team, hours_needed, earliest_start):
	"""Suggest up to 3 days within 30 days of earliest_start where the team
	has at least `hours_needed` of unbooked scheduled capacity."""
	from field_services.field_services.doctype.team_schedule.team_schedule import (
		get_available_hours,
		get_booked_hours,
	)

	hours_needed = flt(hours_needed)
	start = getdate(earliest_start)
	suggestions = []

	for i in range(30):
		day = add_days(start, i)
		scheduled = get_available_hours(team, day, day)["total_hours"]
		if scheduled <= 0:
			continue
		booked = get_booked_hours(team, day, day)
		available = scheduled - booked
		if available >= hours_needed:
			start_dt = _earliest_shift_start(team, day)
			if not start_dt:
				continue
			end_dt = add_to_date(start_dt, hours=hours_needed)
			suggestions.append({
				"start": str(start_dt),
				"end": str(end_dt),
				"available_hours": available,
			})
			if len(suggestions) >= 3:
				break

	return suggestions


def _earliest_shift_start(team, day):
	"""The earliest shift start datetime on `day` across the team's active
	schedules that cover that weekday."""
	weekday = day.strftime("%A")
	schedules = frappe.get_all(
		"Team Schedule",
		filters={"service_team": team, "status": "Active"},
		fields=["name", "shift_type", "start_date", "end_date"],
	)
	earliest = None
	for s in schedules:
		if day < getdate(s.start_date):
			continue
		if s.end_date and day > getdate(s.end_date):
			continue
		days = frappe.get_all(
			"Schedule Day", filters={"parent": s.name, "parenttype": "Team Schedule"}, pluck="day"
		)
		if weekday not in days:
			continue
		start_time = frappe.db.get_value("FS Shift Type", s.shift_type, "start_time")
		if start_time is None:
			continue
		start_dt = get_datetime(f"{day} {start_time}")
		if earliest is None or start_dt < earliest:
			earliest = start_dt
	return earliest


@frappe.whitelist()
def create_project_booking(project, team, start, end, override_reason=None):
	"""Create a Project Booking and link it back to the Project."""
	booked_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	booking = frappe.get_doc({
		"doctype": "Project Booking",
		"project": project,
		"service_team": team,
		"booking_start": start,
		"booking_end": end,
		"override_reason": override_reason,
		"booked_by": booked_by,
		"status": "Tentative",
	})
	booking.insert(ignore_permissions=True)

	frappe.db.set_value("Project", project, {
		"project_booking": booking.name,
		"service_team": team,
	})
	return booking
