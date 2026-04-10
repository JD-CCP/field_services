import frappe
import requests

# Whitelisted methods for Field Services portals


@frappe.whitelist()
def geocode_address(address):
	"""Geocode an address string using OpenStreetMap Nominatim.

	Returns a dict with lat/lng/display_name or None if not found.
	"""
	if not address:
		return None

	try:
		response = requests.get(
			"https://nominatim.openstreetmap.org/search",
			params={
				"q": address,
				"format": "json",
				"limit": 1,
			},
			headers={
				"User-Agent": "FieldServices/1.0 (Frappe App - CompuCable Projects)"
			},
			timeout=10,
		)
		response.raise_for_status()
		results = response.json()
		if results:
			return {
				"lat": float(results[0]["lat"]),
				"lng": float(results[0]["lon"]),
				"display_name": results[0].get("display_name"),
			}
	except Exception as e:
		frappe.log_error(f"Geocoding failed: {e}", "Nominatim Geocode")

	return None
