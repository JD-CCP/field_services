// Field Services additions to the core Project form.
// Loaded via the doctype_js hook (see hooks.py) so no core file is touched.

frappe.ui.form.on("Project", {
	refresh: function (frm) {
		// Show linked Field Job Cards in Connections. (Material Request is
		// already shown by ERPNext's core Project dashboard via the
		// item-level project link, so we don't re-add it here.)
		// frm.dashboard is reset on each refresh, so this is safe to re-add.
		frm.dashboard.add_transactions({
			label: __("Field Services"),
			items: ["Field Job Card"],
		});

		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Create Material Request"), function () {
			open_material_request_dialog(frm);
		});

		frm.add_custom_button(__("Schedule Field Service"), function () {
			frappe.new_doc("Field Service Booking", {
				project: frm.doc.name,
				customer: frm.doc.customer,
				project_type: frm.doc.project_type,
				service_team: frm.doc.service_team,
			});
		});
	},
});

function open_material_request_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Create Material Request"),
		size: "extra-large",
		fields: [
			{
				fieldtype: "Select",
				fieldname: "import_source",
				label: __("Import Source"),
				options: ["Manual", "From Sales Order", "From Service BOM"].join("\n"),
				default: "Manual",
				reqd: 1,
				onchange: function () {
					// Clear the table whenever the source changes
					set_items(d, []);
				},
			},
			{
				fieldtype: "Link",
				fieldname: "sales_order",
				label: __("Sales Order"),
				options: "Sales Order",
				depends_on: "eval:doc.import_source=='From Sales Order'",
				get_query: function () {
					return { filters: { project: frm.doc.name } };
				},
				onchange: function () {
					const so = d.get_value("sales_order");
					if (!so) return;
					frappe.db.get_doc("Sales Order", so).then(function (doc) {
						set_items(
							d,
							(doc.items || []).map(function (it) {
								return {
									item_code: it.item_code,
									item_name: it.item_name,
									qty: it.qty,
									uom: it.uom,
									rate: it.rate,
								};
							})
						);
					});
				},
			},
			{
				fieldtype: "Section Break",
				depends_on: "eval:doc.import_source=='From Service BOM'",
			},
			{
				fieldtype: "Link",
				fieldname: "service_bom",
				label: __("Service BOM"),
				options: "Service BOM",
				depends_on: "eval:doc.import_source=='From Service BOM'",
				get_query: function () {
					return { filters: { is_active: 1 } };
				},
				onchange: function () {
					load_bom_items(d);
				},
			},
			{
				fieldtype: "Float",
				fieldname: "bom_qty",
				label: __("Quantity"),
				default: 1,
				depends_on: "eval:doc.import_source=='From Service BOM'",
				onchange: function () {
					load_bom_items(d);
				},
			},
			{ fieldtype: "Section Break", label: __("Target") },
			{
				fieldtype: "Link",
				fieldname: "target_warehouse",
				label: __("Target Warehouse"),
				options: "Warehouse",
				reqd: 1,
				description: __("Defaults to the project team's store; materials are transferred here"),
			},
			{ fieldtype: "Section Break", label: __("Items") },
			{
				fieldtype: "Table",
				fieldname: "items",
				label: __("Items"),
				cannot_add_rows: false,
				in_place_edit: false,
				data: [],
				fields: [
					{
						fieldtype: "Link",
						fieldname: "item_code",
						label: __("Item"),
						options: "Item",
						in_list_view: 1,
						columns: 3,
						reqd: 1,
						onchange: function () {
							// nothing; item_name fetched on create
						},
					},
					{
						fieldtype: "Data",
						fieldname: "item_name",
						label: __("Item Name"),
						in_list_view: 1,
						columns: 3,
						read_only: 1,
					},
					{
						fieldtype: "Float",
						fieldname: "qty",
						label: __("Qty"),
						in_list_view: 1,
						columns: 2,
						reqd: 1,
					},
					{
						fieldtype: "Link",
						fieldname: "uom",
						label: __("UOM"),
						options: "UOM",
						in_list_view: 1,
						columns: 2,
					},
					{
						fieldtype: "Currency",
						fieldname: "rate",
						label: __("Rate"),
						in_list_view: 1,
						columns: 2,
					},
				],
			},
		],
		primary_action_label: __("Create"),
		primary_action: function () {
			create_material_request(frm, d);
		},
	});

	// Default the target warehouse to the project team's store
	if (frm.doc.service_team) {
		frappe.db.get_value("Service Team", frm.doc.service_team, "team_warehouse").then(function (r) {
			if (r && r.message && r.message.team_warehouse) {
				d.set_value("target_warehouse", r.message.team_warehouse);
			}
		});
	}

	d.add_custom_action(__("Add More Items"), function () {
		const data = d.fields_dict.items.grid.get_data() || [];
		data.push({});
		d.fields_dict.items.df.data = data;
		d.fields_dict.items.grid.refresh();
	});

	d.show();
}

function set_items(d, rows) {
	d.fields_dict.items.df.data = rows || [];
	d.fields_dict.items.grid.refresh();
}

function load_bom_items(d) {
	const bom = d.get_value("service_bom");
	const qty = d.get_value("bom_qty") || 1;
	if (!bom) return;

	frappe.call({
		method: "field_services.api.explode_service_bom",
		args: { service_bom: bom, qty: qty },
		freeze: true,
		freeze_message: __("Loading BOM items..."),
		callback: function (r) {
			set_items(
				d,
				(r.message || []).map(function (it) {
					return {
						item_code: it.item_code,
						item_name: it.item_name,
						qty: it.qty,
						uom: it.uom,
						rate: it.rate,
					};
				})
			);
		},
	});
}

function create_material_request(frm, d) {
	const items = (d.fields_dict.items.grid.get_data() || []).filter(function (r) {
		return r.item_code;
	});
	if (!items.length) {
		frappe.msgprint(__("Please add at least one item."));
		return;
	}

	const target_warehouse = d.get_value("target_warehouse");
	if (!target_warehouse) {
		frappe.msgprint(__("Please set a Target Warehouse."));
		return;
	}

	const today = frappe.datetime.get_today();
	frappe.call({
		method: "frappe.client.insert",
		freeze: true,
		freeze_message: __("Creating Material Request..."),
		args: {
			doc: {
				doctype: "Material Request",
				material_request_type: "Material Transfer",
				schedule_date: today,
				set_warehouse: target_warehouse,
				items: items.map(function (r) {
					return {
						item_code: r.item_code,
						qty: r.qty || 1,
						uom: r.uom,
						schedule_date: today,
						warehouse: target_warehouse,
						project: frm.doc.name,
					};
				}),
			},
		},
		callback: function (r) {
			if (r.message) {
				d.hide();
				frappe.show_alert({
					message: __("Material Request {0} created", [r.message.name]),
					indicator: "green",
				});
				frappe.set_route("Form", "Material Request", r.message.name);
			}
		},
	});
}
