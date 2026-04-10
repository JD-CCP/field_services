import frappe
import requests

# Whitelisted methods for Field Services portals


NOMINATIM_HEADERS = {
	"User-Agent": "FieldServices/1.0 (Frappe App - CompuCable Projects)"
}


@frappe.whitelist()
def search_address(query):
	"""Search for address suggestions using OpenStreetMap Nominatim.

	Returns a list of suggestion dicts with parsed address components.
	"""
	if not query or len(query) < 3:
		return []

	try:
		response = requests.get(
			"https://nominatim.openstreetmap.org/search",
			params={
				"q": query,
				"format": "json",
				"addressdetails": 1,
				"limit": 5,
			},
			headers=NOMINATIM_HEADERS,
			timeout=10,
		)
		response.raise_for_status()
		results = response.json()
	except Exception as e:
		frappe.log_error(f"Address search failed: {e}", "Nominatim Search")
		return []

	suggestions = []
	for r in results:
		addr = r.get("address", {})
		line1_parts = [addr.get("house_number"), addr.get("road")]
		line1 = " ".join(p for p in line1_parts if p)
		line2 = addr.get("suburb") or addr.get("neighbourhood") or addr.get("hamlet") or ""
		city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or ""

		suggestions.append(
			{
				"display_name": r.get("display_name"),
				"lat": float(r.get("lat")) if r.get("lat") else None,
				"lng": float(r.get("lon")) if r.get("lon") else None,
				"address_line1": line1,
				"address_line2": line2,
				"city": city,
				"state": addr.get("state") or "",
				"pincode": addr.get("postcode") or "",
				"country": addr.get("country") or "",
			}
		)

	return suggestions


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
			headers=NOMINATIM_HEADERS,
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
