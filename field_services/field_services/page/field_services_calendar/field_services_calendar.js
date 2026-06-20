frappe.pages["field-services-calendar"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Field Services Calendar"),
		single_column: true,
	});
	new FieldServicesCalendar(page);
};

const STATUS_COLOURS = {
	Tentative: { bg: "#2196F3", fg: "#fff" },
	Confirmed: { bg: "#4CAF50", fg: "#fff" },
	"In Progress": { bg: "#FFC107", fg: "#212121" },
	Completed: { bg: "#9E9E9E", fg: "#fff" },
	Overdue: { bg: "#F44336", fg: "#fff" },
};

class FieldServicesCalendar {
	constructor(page) {
		this.page = page;
		this.view = "Week";
		this.anchor = frappe.datetime.now_date(true); // moment
		this.region = null;
		this.make_controls();
		this.body = $('<div class="fsc-body"></div>').appendTo(this.page.main);
		this.inject_styles();
		this.refresh();
	}

	make_controls() {
		this.region_field = this.page.add_field({
			fieldname: "region",
			label: __("Service Region"),
			fieldtype: "Link",
			options: "Service Region",
			change: () => {
				this.region = this.region_field.get_value();
				this.refresh();
			},
		});

		this.page.set_primary_action(__("Today"), () => {
			this.anchor = frappe.datetime.now_date(true);
			this.refresh();
		});
		this.page.add_button(__("◀"), () => this.shift(-1));
		this.page.add_button(__("▶"), () => this.shift(1));

		this.week_btn = this.page.add_button(__("Week"), () => this.set_view("Week"));
		this.month_btn = this.page.add_button(__("Month"), () => this.set_view("Month"));
	}

	set_view(v) {
		this.view = v;
		this.refresh();
	}

	shift(dir) {
		const unit = this.view === "Week" ? "weeks" : "months";
		this.anchor = moment(this.anchor).add(dir, unit);
		this.refresh();
	}

	range() {
		if (this.view === "Week") {
			const start = moment(this.anchor).startOf("isoWeek");
			return { start, end: moment(start).add(6, "days") };
		}
		const start = moment(this.anchor).startOf("month");
		return { start, end: moment(this.anchor).endOf("month") };
	}

	columns(start, end) {
		const cols = [];
		let d = moment(start);
		while (d.isSameOrBefore(end, "day")) {
			cols.push(moment(d));
			d = d.add(1, "day");
		}
		return cols;
	}

	refresh() {
		const { start, end } = this.range();
		const sd = start.format("YYYY-MM-DD");
		const ed = end.format("YYYY-MM-DD");
		this.page.set_indicator(
			`${start.format("D MMM")} – ${end.format("D MMM YYYY")}`,
			"blue"
		);
		frappe.call({
			method: "field_services.api.get_calendar_data",
			args: { start_date: sd, end_date: ed, region: this.region || undefined },
			callback: (r) => this.render(r.message || { teams: [], bookings: [] }, start, end),
		});
	}

	render(data, start, end) {
		const cols = this.columns(start, end);
		const now = moment();

		// group bookings by team
		const by_team = {};
		(data.bookings || []).forEach((b) => {
			(by_team[b.service_team] = by_team[b.service_team] || []).push(b);
		});

		let html = '<table class="fsc-table"><thead><tr>';
		html += `<th class="fsc-team-col">${__("Team")}</th>`;
		cols.forEach((c) => {
			const today = c.isSame(now, "day") ? " fsc-today" : "";
			html += `<th class="fsc-day${today}">${c.format("ddd")}<br><span class="fsc-daynum">${c.format("D MMM")}</span></th>`;
		});
		html += "</tr></thead><tbody>";

		if (!data.teams.length) {
			html += `<tr><td colspan="${cols.length + 1}" class="text-muted text-center" style="padding:20px;">${__("No teams found")}</td></tr>`;
		}

		data.teams.forEach((t) => {
			html += "<tr>";
			const avail = flt(t.available_hours, 1);
			const total = flt(t.total_hours, 1);
			const ind = avail <= 0 ? "red" : avail < total / 2 ? "orange" : "green";
			html += `<td class="fsc-team-col">
				<div class="fsc-team-name">${frappe.utils.escape_html(t.team_name || t.name)}</div>
				<div class="fsc-avail"><span class="indicator-pill ${ind}">${avail} / ${total} ${__("hrs free")}</span></div>
			</td>`;

			cols.forEach((c) => {
				html += '<td class="fsc-cell">';
				(by_team[t.name] || []).forEach((b) => {
					const bs = moment(b.booking_start);
					const be = moment(b.booking_end);
					if (c.isBetween(bs.clone().startOf("day").subtract(1, "ms"), be.clone().endOf("day"))) {
						html += this.block_html(b, now);
					}
				});
				html += "</td>";
			});
			html += "</tr>";
		});
		html += "</tbody></table>";

		this.body.html(html);

		// click-to-open
		this.body.find(".fsc-block").on("click", function () {
			const project = $(this).data("project");
			if (project) frappe.set_route("Form", "Project", project);
		});
	}

	block_html(b, now) {
		let status = b.status;
		if (status !== "Completed" && moment(b.booking_end).isBefore(now)) {
			status = "Overdue";
		}
		const c = STATUS_COLOURS[status] || STATUS_COLOURS.Tentative;
		const hrs = flt(b.booked_hours, 1);
		const cust = b.customer ? `<div class="fsc-sub">${frappe.utils.escape_html(b.customer)}</div>` : "";
		return `<div class="fsc-block" data-project="${frappe.utils.escape_html(b.project)}"
			title="${frappe.utils.escape_html(status)} · ${hrs} hrs"
			style="background:${c.bg};color:${c.fg};">
			<div class="fsc-title">${frappe.utils.escape_html(b.project_name || b.project)}</div>
			${cust}
			<div class="fsc-sub">${hrs} ${__("hrs")} · ${frappe.utils.escape_html(status)}</div>
		</div>`;
	}

	inject_styles() {
		if (document.getElementById("fsc-styles")) return;
		const css = `
		.fsc-body { overflow-x: auto; padding: 8px 0; }
		.fsc-table { border-collapse: collapse; width: 100%; min-width: 720px; }
		.fsc-table th, .fsc-table td { border: 1px solid var(--border-color); vertical-align: top; }
		.fsc-table th { padding: 6px 8px; background: var(--bg-light-gray); font-weight: 600; text-align: center; font-size: 12px; }
		.fsc-daynum { font-weight: 400; color: var(--text-muted); font-size: 11px; }
		.fsc-today { background: var(--blue-100) !important; }
		.fsc-team-col { width: 180px; min-width: 160px; padding: 8px; background: var(--fg-color); position: sticky; left: 0; z-index: 1; }
		.fsc-team-name { font-weight: 600; }
		.fsc-avail { margin-top: 4px; font-size: 11px; }
		.fsc-cell { min-width: 90px; height: 56px; padding: 3px; }
		.fsc-block { border-radius: 4px; padding: 4px 6px; margin-bottom: 3px; cursor: pointer; font-size: 11px; line-height: 1.25; }
		.fsc-block:hover { opacity: 0.9; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
		.fsc-title { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		.fsc-sub { opacity: 0.92; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
		`;
		$(`<style id="fsc-styles">${css}</style>`).appendTo("head");
	}
}
