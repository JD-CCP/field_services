function check_member_conflict(frm, employee, on_cancel, on_proceed) {
	if (!employee) {
		if (on_proceed) on_proceed();
		return;
	}

	frappe.call({
		method: 'field_services.field_services.doctype.service_team.service_team.get_member_conflicts',
		args: { team: frm.doc.name || '', employee },
		callback: (r) => {
			const conflicts = r.message || [];
			if (!conflicts.length) {
				if (on_proceed) on_proceed();
				return;
			}

			const teams = conflicts.map(t => `<b>${frappe.utils.escape_html(t.team_name)}</b>`).join(', ');
			let resolved = false;
			const d = new frappe.ui.Dialog({
				title: __('Already Allocated'),
				fields: [{
					fieldtype: 'HTML',
					options: `<p>${__('This employee is already a member of')}: ${teams}.</p>
						<p>${__('Reassigning will remove them from their current team and add them here on save.')}</p>`
				}],
				primary_action_label: __('Reassign Here'),
				primary_action() {
					resolved = true;
					frm.set_value('reassign_on_conflict', 1);
					d.hide();
					if (on_proceed) on_proceed();
				},
				secondary_action_label: __('Cancel'),
				secondary_action() {
					resolved = true;
					d.hide();
					if (on_cancel) on_cancel();
				}
			});
			d.onhide = () => { if (!resolved && on_cancel) on_cancel(); };
			d.show();
		}
	});
}

function apply_team_lead_to_members(frm) {
	if (!frm.doc.team_lead) return;

	const existing = (frm.doc.members || []).find(
		m => m.employee === frm.doc.team_lead
	);

	(frm.doc.members || []).forEach(m => {
		if (m.role === 'Lead' && m.employee !== frm.doc.team_lead) {
			frappe.model.set_value(m.doctype, m.name, 'role', 'Technician');
		}
	});

	if (existing) {
		frappe.model.set_value(existing.doctype, existing.name, 'role', 'Lead');
	} else {
		frm.add_child('members', {
			employee: frm.doc.team_lead,
			role: 'Lead',
			is_active: 1
		});
		frm.refresh_field('members');
	}
}

frappe.ui.form.on('Service Team', {
	setup(frm) {
		// Only warehouses flagged as Field Service Stores can be a team store
		frm.set_query('team_warehouse', function () {
			return { filters: { is_field_service_store: 1 } };
		});
	},

	team_lead(frm) {
		// suppress recursive trigger while we clear the value on cancel
		if (frm._skip_team_lead_check) {
			frm._skip_team_lead_check = false;
			return;
		}
		if (!frm.doc.team_lead) return;

		check_member_conflict(frm, frm.doc.team_lead,
			() => {
				frm._skip_team_lead_check = true;
				frm.set_value('team_lead', null);
			},
			() => apply_team_lead_to_members(frm)
		);
	}
});

frappe.ui.form.on('Service Team Member', {
	employee(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row._skip_conflict_check) {
			row._skip_conflict_check = false;
			return;
		}
		if (!row.employee) return;

		check_member_conflict(frm, row.employee,
			() => {
				row._skip_conflict_check = true;
				frappe.model.set_value(cdt, cdn, 'employee', null);
			},
			null
		);
	}
});
