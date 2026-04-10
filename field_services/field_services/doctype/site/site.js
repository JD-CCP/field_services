// Copyright (c) 2026, CompuCable Projects CC and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site", {
	address: function (frm) {
		if (!frm.doc.address) {
			frm.set_value("address_display", "");
			return;
		}

		frappe.db.get_doc("Address", frm.doc.address).then((addr) => {
			const lines = [
				addr.address_line1,
				addr.address_line2,
				[addr.city, addr.state, addr.pincode].filter(Boolean).join(", "),
				addr.country,
			].filter(Boolean);

			frm.set_value("address_display", lines.join("\n"));

			const address_str = lines.join(", ");
			if (!address_str) {
				return;
			}

			frappe.call({
				method: "field_services.api.geocode_address",
				args: { address: address_str },
				freeze: true,
				freeze_message: __("Locating address on map..."),
				callback: function (r) {
					if (r.message && r.message.lat && r.message.lng) {
						const geojson = {
							type: "FeatureCollection",
							features: [
								{
									type: "Feature",
									properties: {},
									geometry: {
										type: "Point",
										coordinates: [r.message.lng, r.message.lat],
									},
								},
							],
						};
						frm.set_value("gps_coordinates", JSON.stringify(geojson));
						frappe.show_alert({
							message: __("Location set from address"),
							indicator: "green",
						});
					} else {
						frappe.show_alert({
							message: __("Could not find location for address. Please set manually."),
							indicator: "orange",
						});
					}
				},
			});
		});
	},
});
