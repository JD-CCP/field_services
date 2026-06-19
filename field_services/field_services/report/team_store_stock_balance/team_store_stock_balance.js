// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.query_reports["Team Store Stock Balance"] = {
	filters: [
		{
			fieldname: "service_team",
			label: __("Service Team"),
			fieldtype: "Link",
			options: "Service Team",
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
	],
};
