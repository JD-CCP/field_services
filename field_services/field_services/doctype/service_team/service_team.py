import frappe
from frappe.model.document import Document


class ServiceTeam(Document):
	def validate(self):
		self._sync_team_lead_member()
		self._check_member_conflicts()

	def before_save(self):
		if not self.team_warehouse:
			self.team_warehouse = self._get_or_create_team_warehouse()

	def _warehouse_company(self):
		return frappe.defaults.get_defaults().get("company")

	def _parent_warehouse(self, company):
		if self.service_region:
			region_wh = frappe.db.get_value("Service Region", self.service_region, "default_warehouse")
			if region_wh:
				return region_wh
		return frappe.db.get_single_value("Stock Settings", "default_warehouse") or ""

	def _get_or_create_team_warehouse(self):
		"""Reuse an existing FS team store for this team/company if present,
		otherwise create one. Reuse avoids the duplicate-name crash that
		happened when the existence check ignored the company abbr suffix."""
		company = self._warehouse_company()
		base_name = f"FS-{self.team_name} - Store"

		# already exists for this company (by base name or abbr-suffixed name)?
		existing = frappe.db.get_value(
			"Warehouse", {"warehouse_name": base_name, "company": company}, "name"
		)
		if existing:
			return existing
		abbr = frappe.get_cached_value("Company", company, "abbr") if company else None
		if abbr and frappe.db.exists("Warehouse", f"{base_name} - {abbr}"):
			return f"{base_name} - {abbr}"

		wh = frappe.get_doc({
			"doctype": "Warehouse",
			"warehouse_name": base_name,
			"parent_warehouse": self._parent_warehouse(company),
			"company": company,
		})
		wh.insert(ignore_permissions=True)
		return wh.name

	@frappe.whitelist()
	def create_team_warehouse(self):
		"""Assign (or create) this team's store on demand from the form."""
		if self.team_warehouse:
			return {"team_warehouse": self.team_warehouse, "created": False}
		self.team_warehouse = self._get_or_create_team_warehouse()
		self.save()
		return {"team_warehouse": self.team_warehouse, "created": True}

	def _sync_team_lead_member(self):
		if not self.team_lead:
			return

		lead_row = None
		for m in self.members or []:
			if m.employee == self.team_lead:
				lead_row = m
			elif m.role == 'Lead':
				m.role = 'Technician'

		if lead_row:
			lead_row.role = 'Lead'
		else:
			self.append('members', {
				'employee': self.team_lead,
				'role': 'Lead',
				'is_active': 1
			})

	def _check_member_conflicts(self):
		employees = [m.employee for m in (self.members or []) if m.is_active and m.employee]
		if not employees:
			self.reassign_on_conflict = 0
			return

		rows = frappe.db.sql("""
			SELECT stm.employee, st.name AS team, st.team_name, st.team_lead, emp.employee_name
			FROM `tabService Team Member` stm
			INNER JOIN `tabService Team` st ON st.name = stm.parent
			LEFT JOIN `tabEmployee` emp ON emp.name = stm.employee
			WHERE stm.employee IN %(employees)s
			  AND stm.is_active = 1
			  AND st.name != %(team)s
		""", {'employees': employees, 'team': self.name or ''}, as_dict=True)

		if not rows:
			self.reassign_on_conflict = 0
			return

		if self.reassign_on_conflict:
			self._reassign_from_other_teams(rows)
			self.reassign_on_conflict = 0
			return

		items = ''.join(
			f"<li>{r.employee_name or r.employee} is already on <b>{r.team_name}</b></li>"
			for r in rows
		)
		frappe.throw(
			f"<p>The following employees are already allocated to another team:</p><ul>{items}</ul>"
			"<p>Re-add the member to choose an override and reassign them here.</p>",
			title="Duplicate Team Assignment"
		)

	def _reassign_from_other_teams(self, conflict_rows):
		# refuse if the employee is the lead of the other team — that field is required
		lead_blocks = [r for r in conflict_rows if r.team_lead == r.employee]
		if lead_blocks:
			items = ''.join(
				f"<li>{r.employee_name or r.employee} is the lead of <b>{r.team_name}</b></li>"
				for r in lead_blocks
			)
			frappe.throw(
				f"<p>Cannot auto-reassign — these employees are team leads on their current team:</p><ul>{items}</ul>"
				"<p>Please update the other team first (assign a new lead) before reassigning.</p>",
				title="Cannot Reassign Team Lead"
			)

		from collections import defaultdict
		per_team = defaultdict(set)
		for r in conflict_rows:
			per_team[r.team].add(r.employee)

		for team_name, emps in per_team.items():
			other = frappe.get_doc('Service Team', team_name)
			other.members = [m for m in other.members if m.employee not in emps]
			other.save(ignore_permissions=True)


@frappe.whitelist()
def get_member_conflicts(team, employee):
	"""Return active Service Teams (other than `team`) where `employee` is a member."""
	if not employee:
		return []

	return frappe.db.sql("""
		SELECT st.name, st.team_name
		FROM `tabService Team Member` stm
		INNER JOIN `tabService Team` st ON st.name = stm.parent
		WHERE stm.employee = %(employee)s
		  AND stm.is_active = 1
		  AND st.name != %(team)s
	""", {'employee': employee, 'team': team or ''}, as_dict=True)
