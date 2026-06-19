# Copyright (c) 2026, CompuCable Projects CC and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_time


class FSShiftType(Document):
	def validate(self):
		self.calculate_hours()

	def calculate_hours(self):
		"""Hours between start and end, treating end <= start as an
		overnight shift (e.g. 15:00 -> 00:00 = 9 hours)."""
		if not self.start_time or not self.end_time:
			self.hours = 0
			return

		start = get_time(self.start_time)
		end = get_time(self.end_time)
		start_sec = start.hour * 3600 + start.minute * 60 + start.second
		end_sec = end.hour * 3600 + end.minute * 60 + end.second
		if end_sec <= start_sec:
			end_sec += 24 * 3600  # overnight
		self.hours = (end_sec - start_sec) / 3600.0
