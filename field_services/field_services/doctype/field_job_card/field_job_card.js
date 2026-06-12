// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Job Card", {
	refresh: function (frm) {
		setup_clock_buttons(frm);

		frm.fields_dict.photos.grid.add_custom_button(__("Upload Photos"), function () {
			if (frm.is_new()) {
				frappe.msgprint(__("Please save the Job Card before uploading photos."));
				return;
			}

			new frappe.ui.FileUploader({
				doctype: frm.doctype,
				docname: frm.docname,
				folder: "Home/Attachments",
				allow_multiple: true,
				restrictions: {
					allowed_file_types: ["image/*"],
				},
				on_success: function (file_doc) {
					frm.add_child("photos", {
						photo: file_doc.file_url,
					});
					frm.refresh_field("photos");
					frm.dirty();
				},
			});
		});
	},
});

function setup_clock_buttons(frm) {
	if (frm.is_new() || frm.doc.status === "Completed" || frm.doc.status === "Cancelled") {
		return;
	}

	const call_clock_method = function (method, freeze_message) {
		frappe.call({
			method: "field_services.api." + method,
			args: { job_card: frm.docname },
			freeze: true,
			freeze_message: freeze_message,
			callback: function () {
				frm.reload_doc();
			},
		});
	};

	if (frm.doc.status === "Open") {
		frm.page.set_primary_action(__("Clock In"), function () {
			call_clock_method("clock_in", __("Clocking in..."));
		});
	} else if (frm.doc.status === "Work In Progress") {
		frm.add_custom_button(__("Pause"), function () {
			call_clock_method("pause_job", __("Pausing..."));
		});
		frm.page.set_primary_action(__("Clock Out"), function () {
			frappe.confirm(
				__("Clock out and complete this Job Card? This will log time to the team's timesheets."),
				function () {
					call_clock_method("clock_out", __("Clocking out..."));
				}
			);
		});
	} else if (frm.doc.status === "Paused") {
		frm.add_custom_button(__("Resume"), function () {
			call_clock_method("resume_job", __("Resuming..."));
		});
		frm.page.set_primary_action(__("Clock Out"), function () {
			frappe.confirm(
				__("Clock out and complete this Job Card? This will log time to the team's timesheets."),
				function () {
					call_clock_method("clock_out", __("Clocking out..."));
				}
			);
		});
	}
}
