frappe.pages["field-services-dispatch"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Field Services Dispatch"),
		single_column: true,
	});
	new FieldServicesDispatch(page);
};

const PRIORITY_COLOUR = { 1: "#B71C1C", 2: "#E65100", 3: "#1565C0", 4: "#2E7D32", 5: "#616161" };
const STATUS_COLOUR = {
	Draft: "#9E9E9E", Tentative: "#2196F3", "Pre-Scheduled": "#7E57C2",
	Confirmed: "#4CAF50", Dispatched: "#00897B", "In Progress": "#FFC107",
	Completed: "#607D8B", Cancelled: "#BDBDBD",
};

class FieldServicesDispatch {
	constructor(page) {
		this.page = page;
		this.view = "Today";
		this.anchor = frappe.datetime.now_date(true);
		this.region = null;
		this.make_controls();
		this.body = $('<div class="fsd-body"></div>').appendTo(this.page.main);
		this.inject_styles();
		this.refresh();
	}

	make_controls() {
		this.region_field = this.page.add_field({
			fieldname: "region", label: __("Service Region"),
			fieldtype: "Link", options: "Service Region",
			change: () => { this.region = this.region_field.get_value(); this.refresh(); },
		});
		this.page.set_primary_action(__("Today"), () => {
			this.anchor = frappe.datetime.now_date(true); this.refresh();
		});
		this.page.add_button(__("◀"), () => this.shift(-1));
		this.page.add_button(__("▶"), () => this.shift(1));
		["Today", "Week", "Month"].forEach((v) =>
			this.page.add_button(__(v), () => { this.view = v; this.refresh(); })
		);
		this.page.add_menu_item(__("New Booking"), () => frappe.new_doc("Field Service Booking"));
	}

	shift(dir) {
		const unit = this.view === "Today" ? "days" : this.view === "Week" ? "weeks" : "months";
		this.anchor = moment(this.anchor).add(dir, unit);
		this.refresh();
	}

	refresh() {
		const label = this.view === "Month"
			? moment(this.anchor).format("MMMM YYYY")
			: this.view === "Week"
			? `${__("Week of")} ${moment(this.anchor).startOf("isoWeek").format("D MMM")}`
			: moment(this.anchor).format("ddd, D MMM YYYY");
		this.page.set_indicator(`${this.view} · ${label}`, "blue");
		frappe.call({
			method: "field_services.api.get_dispatch_data",
			args: { view: this.view, date: moment(this.anchor).format("YYYY-MM-DD"), region: this.region || undefined },
			callback: (r) => this["render_" + this.view.toLowerCase()](r.message || {}),
		});
	}

	// ---------- Today ----------
	render_today(data) {
		let h = '<table class="fsd-table"><thead><tr><th class="fsd-team-col">' + __("Team") + "</th>";
		["Slot 1", "Slot 2", "Slot 3"].forEach((s) => (h += `<th>${s}</th>`));
		h += "<th>" + __("Alerts") + "</th></tr></thead><tbody>";
		if (!(data.teams || []).length) h += `<tr><td colspan="5" class="text-muted text-center" style="padding:18px">${__("No teams")}</td></tr>`;
		(data.teams || []).forEach((t) => {
			h += `<tr><td class="fsd-team-col"><b>${frappe.utils.escape_html(t.team_name || t.name)}</b></td>`;
			["Slot 1", "Slot 2", "Slot 3"].forEach((s) => {
				const b = t.slots[s];
				h += `<td class="fsd-cell">${b ? this.card(b) : '<span class="text-muted">' + __("Available") + "</span>"}</td>`;
			});
			const al = (t.alerts || []);
			h += `<td class="fsd-cell">${al.length ? '<span class="indicator-pill orange">' + frappe.utils.escape_html(al.join("; ")) + "</span>" : '<span class="text-muted">None</span>'}</td>`;
			h += "</tr>";
			if ((t.unslotted || []).length) {
				h += `<tr><td class="fsd-team-col text-muted">${__("Unslotted")}</td><td colspan="4" class="fsd-cell">${t.unslotted.map((b) => this.card(b)).join("")}</td></tr>`;
			}
		});
		h += "</tbody></table>";
		this.body.html(h);
		this.bind_cards();
	}

	card(b) {
		const pc = PRIORITY_COLOUR[b.scheduling_priority] || "#616161";
		const sc = STATUS_COLOUR[b.schedule_status] || "#9E9E9E";
		const warn = b.readiness_status === "Not Ready" || b.double_booking_status !== "OK";
		const warnHtml = warn ? `<div class="fsd-warn">⚠ ${frappe.utils.escape_html(b.alert_message || "")}</div>` : "";
		return `<div class="fsd-card" data-project="${frappe.utils.escape_html(b.project || "")}" style="border-left:4px solid ${pc}">
			<div class="fsd-card-top"><b>${frappe.utils.escape_html(b.project_name || b.project || b.name)}</b>
			<span class="fsd-pill" style="background:${sc}">${frappe.utils.escape_html(b.schedule_status)}</span></div>
			<div class="fsd-sub">${frappe.utils.escape_html(b.customer || "")} ${b.site_area ? "· " + frappe.utils.escape_html(b.site_area) : ""}</div>
			<div class="fsd-sub">${frappe.utils.escape_html(b.project_type || "")} ${b.work_type ? "· " + frappe.utils.escape_html(b.work_type) : ""}</div>
			<div class="fsd-sub">${frappe.utils.escape_html(b.time_range || "")}</div>
			${warnHtml}
		</div>`;
	}

	// ---------- Week ----------
	render_week(data) {
		let h = '<table class="fsd-table"><thead><tr><th class="fsd-team-col">' + __("Team") + "</th>";
		(data.days || []).forEach((d) => (h += `<th>${moment(d).format("ddd D")}</th>`));
		h += "</tr></thead><tbody>";
		(data.teams || []).forEach((t) => {
			h += `<tr><td class="fsd-team-col"><b>${frappe.utils.escape_html(t.team_name || t.name)}</b></td>`;
			(t.days || []).forEach((c) => {
				const cls = c.booked === 0 ? "green" : c.free === 0 ? "red" : "orange";
				const txt = c.booked === 0 ? __("Available") : `${c.booked} booked / ${c.free} free`;
				const tent = c.tentative ? ` <span class="text-muted">(${c.tentative} tent.)</span>` : "";
				h += `<td class="fsd-cell"><span class="indicator-pill ${cls}">${txt}</span>${tent}</td>`;
			});
			h += "</tr>";
		});
		h += "</tbody></table>";
		this.body.html(h);
	}

	// ---------- Month ----------
	render_month(data) {
		const days = data.days || [];
		let h = '<div class="fsd-month">';
		["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach((d) => (h += `<div class="fsd-mh">${d}</div>`));
		if (days.length) {
			const lead = (moment(days[0].date).isoWeekday() - 1);
			for (let i = 0; i < lead; i++) h += '<div class="fsd-mcell fsd-empty"></div>';
		}
		days.forEach((c) => {
			const prob = c.blocked > 0 ? " fsd-prob" : "";
			h += `<div class="fsd-mcell${prob}">
				<div class="fsd-mnum">${c.day_num}</div>
				<div class="fsd-mrow">${c.booked}/${c.total_slots} ${__("slots")}</div>
				${c.p1p2 ? `<div class="fsd-mtag" style="color:#B71C1C">${c.p1p2} P1/P2</div>` : ""}
				${c.confirmed ? `<div class="fsd-mtag" style="color:#2E7D32">${c.confirmed} conf.</div>` : ""}
				${c.tentative ? `<div class="fsd-mtag" style="color:#1565C0">${c.tentative} tent.</div>` : ""}
				${c.blocked ? `<div class="fsd-mtag" style="color:#B71C1C">${c.blocked} ⚠</div>` : ""}
				${c.teams_unavailable ? `<div class="fsd-mtag text-muted">${c.teams_unavailable} team off</div>` : ""}
			</div>`;
		});
		h += "</div>";
		this.body.html(h);
	}

	bind_cards() {
		this.body.find(".fsd-card").on("click", function () {
			const p = $(this).data("project");
			if (p) frappe.set_route("Form", "Project", p);
		});
	}

	inject_styles() {
		if (document.getElementById("fsd-styles")) return;
		const css = `
		.fsd-body { overflow-x:auto; padding:8px 0; }
		.fsd-table { border-collapse:collapse; width:100%; min-width:760px; }
		.fsd-table th,.fsd-table td { border:1px solid var(--border-color); vertical-align:top; padding:6px; }
		.fsd-table th { background:var(--bg-light-gray); font-size:12px; text-align:center; }
		.fsd-team-col { width:150px; background:var(--fg-color); position:sticky; left:0; }
		.fsd-cell { min-width:150px; }
		.fsd-card { border-radius:5px; background:var(--bg-light-gray); padding:6px 8px; cursor:pointer; font-size:11px; line-height:1.3; }
		.fsd-card:hover { box-shadow:0 1px 4px rgba(0,0,0,0.25); }
		.fsd-card-top { display:flex; justify-content:space-between; gap:6px; align-items:center; }
		.fsd-pill { color:#fff; border-radius:8px; padding:0 6px; font-size:10px; white-space:nowrap; }
		.fsd-sub { color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
		.fsd-warn { color:#B71C1C; margin-top:3px; font-weight:600; }
		.fsd-month { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; }
		.fsd-mh { text-align:center; font-weight:600; font-size:11px; color:var(--text-muted); padding:4px; }
		.fsd-mcell { border:1px solid var(--border-color); border-radius:5px; min-height:84px; padding:4px 6px; font-size:11px; }
		.fsd-mcell.fsd-empty { border:none; }
		.fsd-mcell.fsd-prob { background:#FFF3F3; }
		.fsd-mnum { font-weight:700; }
		.fsd-mrow { color:var(--text-muted); }
		.fsd-mtag { font-size:10px; }
		`;
		$(`<style id="fsd-styles">${css}</style>`).appendTo("head");
	}
}
