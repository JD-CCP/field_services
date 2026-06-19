// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.query_reports["Material Variance by Project"] = {
	filters: [
		{
			fieldname: "service_region",
			label: __("Service Region"),
			fieldtype: "Link",
			options: "Service Region",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
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
