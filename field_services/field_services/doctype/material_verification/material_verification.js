// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Verification", {
	refresh: function (frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Populate from Project"), function () {
				if (frm.is_new()) {
					frappe.msgprint(__("Please save the Material Verification first."));
					return;
				}
				frm.call("populate_from_project").then(function (r) {
					frm.reload_doc();
					if (r.message) {
						frappe.show_alert({
							message: __("{0} item(s) loaded", [r.message.item_count]),
							indicator: "green",
						});
					}
				});
			});
		}

		// PM approve / reject once submitted and not yet decided
		if (frm.doc.docstatus === 1 && frm.doc.status === "Submitted") {
			frm.add_custom_button(__("PM Approve"), function () {
				prompt_pm_decision(frm, "pm_approve", __("PM Approve"));
			}, __("Actions"));
			frm.add_custom_button(__("PM Reject"), function () {
				prompt_pm_decision(frm, "pm_reject", __("PM Reject"));
			}, __("Actions"));
		}
	},
});

function prompt_pm_decision(frm, method, title) {
	const d = new frappe.ui.Dialog({
		title: title,
		fields: [
			{ fieldtype: "Link", fieldname: "employee", label: __("Employee"), options: "Employee" },
			{ fieldtype: "Text Editor", fieldname: "notes", label: __("Notes") },
		],
		primary_action_label: title,
		primary_action: function (values) {
			frm.call(method, { employee: values.employee, notes: values.notes }).then(function () {
				d.hide();
				frm.reload_doc();
			});
		},
	});
	d.show();
}
