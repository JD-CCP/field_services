// Adds a "Search Address" button to the standard Address form
// that looks up suggestions via OpenStreetMap Nominatim and fills
// the address fields when one is selected.

frappe.ui.form.on("Address", {
	refresh: function (frm) {
		frm.add_custom_button(__("Search Address"), function () {
			show_address_search_dialog(frm);
		});
	},
});

function show_address_search_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Search Address"),
		size: "large",
		fields: [
			{
				fieldtype: "Data",
				fieldname: "search_query",
				label: __("Search"),
				description: __("Type at least 3 characters to see suggestions"),
			},
			{
				fieldtype: "HTML",
				fieldname: "results",
			},
		],
	});

	let timeout = null;

	d.fields_dict.search_query.$input.on("input", function () {
		clearTimeout(timeout);
		const query = $(this).val();
		const $results = d.fields_dict.results.$wrapper;

		if (query.length < 3) {
			$results.html("");
			return;
		}

		timeout = setTimeout(() => {
			$results.html(
				`<div style="padding:10px;color:#888;">${__("Searching...")}</div>`
			);

			frappe.call({
				method: "field_services.api.search_address",
				args: { query: query },
				callback: function (r) {
					const suggestions = r.message || [];
					if (!suggestions.length) {
						$results.html(
							`<div style="padding:10px;color:#888;">${__("No results found")}</div>`
						);
						return;
					}

					const items = suggestions
						.map((s, i) => {
							const summary = [
								s.address_line1,
								s.address_line2,
								s.city,
								s.state,
								s.country,
							]
								.filter(Boolean)
								.join(", ");
							return `
								<div class="address-suggestion" data-idx="${i}"
									 style="padding:10px 12px;border-bottom:1px solid var(--border-color);cursor:pointer;">
									<div style="font-weight:500;">${frappe.utils.escape_html(summary || s.display_name)}</div>
									<div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${frappe.utils.escape_html(s.display_name)}</div>
								</div>
							`;
						})
						.join("");

					$results.html(
						`<div style="max-height:300px;overflow-y:auto;border:1px solid var(--border-color);border-radius:4px;margin-top:8px;">${items}</div>`
					);

					$results.find(".address-suggestion").on("click", function () {
						const idx = $(this).data("idx");
						const selected = suggestions[idx];
						fill_address_fields(frm, selected);
						d.hide();
						frappe.show_alert({
							message: __("Address filled from search"),
							indicator: "green",
						});
					});

					$results.find(".address-suggestion").on("mouseenter", function () {
						$(this).css("background-color", "var(--bg-light-gray)");
					});
					$results.find(".address-suggestion").on("mouseleave", function () {
						$(this).css("background-color", "");
					});
				},
			});
		}, 400);
	});

	d.show();
}

function fill_address_fields(frm, selected) {
	const fields = {
		address_line1: selected.address_line1,
		address_line2: selected.address_line2,
		city: selected.city,
		state: selected.state,
		pincode: selected.pincode,
		country: selected.country,
	};

	for (const [fieldname, value] of Object.entries(fields)) {
		if (value) {
			frm.set_value(fieldname, value);
		}
	}

	if (!frm.doc.address_title && selected.city) {
		frm.set_value("address_title", selected.city);
	}
}
