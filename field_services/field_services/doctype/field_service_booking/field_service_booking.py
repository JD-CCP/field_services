# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate

# Schedule statuses that "lock" a slot and must never be double-booked
LOCKED_STATUSES = ("Pre-Scheduled", "Confirmed", "Dispatched")
PRIORITY_MAP = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


class FieldServiceBooking(Document):
	def validate(self):
		self.set_scheduling_priority()
		self.check_double_booking()
		self.set_readiness()
		self.guard_confirmation()

	# ------------------------------------------------------------------ #
	def set_scheduling_priority(self):
		"""1 = highest (P1) .. 4 (P4), 5 = planning/intake or unknown.
		Derived from the leading P1..P4 token of the Project Type name."""
		token = (self.project_type or "").strip()[:2].upper()
		self.scheduling_priority = PRIORITY_MAP.get(token, 5)

	# ------------------------------------------------------------------ #
	def busy_window(self):
		"""The datetime window the team is occupied for this booking.
		Spans the earliest of depart/site-start to the latest of
		return/site-end, so overnight and multi-day jobs are handled."""
		starts = [get_datetime(t) for t in (self.depart_time, self.site_start_time) if t]
		ends = [get_datetime(t) for t in (self.return_datetime, self.site_end_time) if t]
		start = min(starts) if starts else None
		end = max(ends) if ends else None
		return start, end

	def check_double_booking(self):
		self.double_booking_status = "OK"
		if not self.service_team:
			return
		start, end = self.busy_window()
		if not (start and end):
			return  # not enough time info to compare; readiness flags "Time missing"

		others = frappe.get_all(
			"Field Service Booking",
			filters={
				"service_team": self.service_team,
				"schedule_status": ["!=", "Cancelled"],
				"name": ["!=", self.name or "new"],
			},
			fields=["name", "schedule_status", "depart_time", "site_start_time",
					"site_end_time", "return_datetime"],
		)

		locked_clashes, soft_clashes = [], []
		for o in others:
			o_start = min([get_datetime(t) for t in (o.depart_time, o.site_start_time) if t], default=None)
			o_end = max([get_datetime(t) for t in (o.return_datetime, o.site_end_time) if t], default=None)
			if not (o_start and o_end):
				continue
			if start < o_end and end > o_start:  # overlap
				(locked_clashes if o.schedule_status in LOCKED_STATUSES else soft_clashes).append(o.name)

		if locked_clashes:
			self.double_booking_status = "Clash"
			frappe.throw(
				f"{self.service_team} is already booked (confirmed/scheduled) in this "
				f"time window: {', '.join(locked_clashes)}. Cannot double-book."
			)
		elif soft_clashes:
			self.double_booking_status = "Warning"

	# ------------------------------------------------------------------ #
	def set_readiness(self):
		warnings = []
		if not self.project:
			warnings.append("Project not linked")
		if self.deposit_required and not self.deposit_paid:
			warnings.append("Deposit not paid")
		if not self.client_confirmed:
			warnings.append("Client not confirmed")
		if not self.po_materials_ready:
			warnings.append("PO/materials not ready")
		if not (self.depart_time and self.site_start_time and self.site_end_time and self.return_datetime):
			warnings.append("Time missing")
		# overnight / multi-day job without a return time
		if self.site_end_time and not self.return_datetime:
			warnings.append("Return time missing")
		if self.double_booking_status == "Warning":
			warnings.append("Possible double booking")

		self.readiness_status = "Ready" if not warnings else "Not Ready"
		self.alert_message = "; ".join(dict.fromkeys(warnings)) if warnings else "None"

	# ------------------------------------------------------------------ #
	def guard_confirmation(self):
		"""A booking may only reach Confirmed once readiness checks pass,
		unless a manager override is set."""
		if self.schedule_status == "Confirmed" and self.readiness_status == "Not Ready" and not self.manager_override:
			frappe.throw(
				"Cannot Confirm while readiness checks are incomplete: "
				f"{self.alert_message}. Enable Manager Override to proceed."
			)
