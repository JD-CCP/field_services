// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.query_reports["Unconfirmed Transfers"] = {
	filters: [
		{
			fieldname: "service_team",
			label: __("Service Team"),
			fieldtype: "Link",
			options: "Service Team",
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
	],
};
