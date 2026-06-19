// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.query_reports["Material Verification Summary"] = {
	filters: [
		{
			fieldname: "service_region",
			label: __("Service Region"),
			fieldtype: "Link",
			options: "Service Region",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "deviation_type",
			label: __("Deviation Type"),
			fieldtype: "Select",
			options: ["", "Lost", "Damaged", "Additionally Used", "Other"].join("\n"),
		},
	],
};
