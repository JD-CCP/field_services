// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Service Booking", {
	refresh: function (frm) {
		frm.dashboard.clear_headline();
		if (frm.is_new()) return;

		if (frm.doc.readiness_status === "Not Ready" || frm.doc.double_booking_status !== "OK") {
			const colour = frm.doc.double_booking_status === "Clash" ? "red" : "orange";
			frm.dashboard.set_headline(
				`<span class="indicator ${colour}">${__("Alerts")}: ${frappe.utils.escape_html(frm.doc.alert_message || "")}</span>`
			);
		} else if (frm.doc.readiness_status === "Ready") {
			frm.dashboard.set_headline(`<span class="indicator green">${__("Ready")}</span>`);
		}

		if (frm.doc.project) {
			frm.add_custom_button(__("Open Project"), () => frappe.set_route("Form", "Project", frm.doc.project));
		}
	},
});
