// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Job Card", {
	refresh: function (frm) {
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
