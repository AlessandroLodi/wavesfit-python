"use strict";
const $ = (id) => document.getElementById(id),
  clone = (x) => JSON.parse(JSON.stringify(x));
let config, metadata, state;
const palette = ["#7ca9ff", "#d197e5", "#f2a88b", "#82c59a", "#e6be78"];
function error(e) {
  $("error").textContent = String(e.message || e);
  $("error").hidden = false;
}
async function api(path, data) {
  const r = await fetch(
    path,
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        },
  );
  const d = await r.json();
  if (!r.ok) throw Error(d.error || r.statusText);
  return d;
}
function number(v) {
  return v === null || v === undefined ? "—" : Number(v).toPrecision(6);
}
class Plot {
  constructor(id) {
    this.canvas = $(id);
    this.series = [];
    this.view = null;
    this.labels = ["x", "y"];
    this.canvas.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        if (!this.bounds) return;
        let [a, b] = this.view || this.bounds.x;
        const t = Math.max(
            0,
            Math.min(1, (e.offsetX - 58) / (this.canvas.clientWidth - 78)),
          ),
          c = a + (b - a) * t,
          f = e.deltaY > 0 ? 1.2 : 0.8;
        this.view = [c + (a - c) * f, c + (b - c) * f];
        this.draw();
      },
      { passive: false },
    );
    this.canvas.addEventListener("dblclick", () => {
      this.view = null;
      this.draw();
    });
    this.canvas.addEventListener("mousemove", (e) => {
      if (!this.bounds) return;
      const [a, b] = this.view || this.bounds.x;
      const x =
        a + ((b - a) * (e.offsetX - 58)) / (this.canvas.clientWidth - 78);
      $("hover").textContent =
        this.labels[0] + " = " + number(x) + " · double-click to reset zoom";
    });
    new ResizeObserver(() => this.draw()).observe(this.canvas);
  }
  set(series, labels) {
    this.series = series;
    this.labels = labels;
    this.draw();
  }
  draw() {
    const c = this.canvas,
      w = c.clientWidth,
      h = c.clientHeight,
      d = devicePixelRatio || 1;
    if (w < 1) return;
    c.width = w * d;
    c.height = h * d;
    const g = c.getContext("2d");
    g.scale(d, d);
    g.clearRect(0, 0, w, h);
    const left = 58,
      right = w - 20,
      top = 18,
      bottom = h - 36;
    const finiteSeries = this.series.filter(
      (s) => s.x && s.y && s.x.length && s.x.length === s.y.length,
    );
    if (!finiteSeries.length) {
      g.fillStyle = "#9aaec5";
      g.font = "12px system-ui";
      g.fillText("Waiting for data…", left, top + 25);
      return;
    }
    let xmin = Infinity,
      xmax = -Infinity,
      ymin = Infinity,
      ymax = -Infinity;
    for (const s of finiteSeries)
      for (let i = 0; i < s.x.length; i++) {
        const x = s.x[i],
          y = s.y[i];
        if (Number.isFinite(x) && Number.isFinite(y)) {
          xmin = Math.min(xmin, x);
          xmax = Math.max(xmax, x);
          if (!this.view || (x >= this.view[0] && x <= this.view[1])) {
            ymin = Math.min(ymin, y);
            ymax = Math.max(ymax, y);
          }
        }
      }
    if (xmin === xmax) {
      xmin -= 0.5;
      xmax += 0.5;
    }
    if (!Number.isFinite(ymin)) {
      ymin = 0;
      ymax = 1;
    }
    if (ymin === ymax) {
      ymin -= 0.5;
      ymax += 0.5;
    }
    const pad = (ymax - ymin) * 0.08;
    ymin -= pad;
    ymax += pad;
    this.bounds = { x: [xmin, xmax] };
    [xmin, xmax] = this.view || [xmin, xmax];
    const X = (x) => left + ((x - xmin) / (xmax - xmin)) * (right - left),
      Y = (y) => bottom - ((y - ymin) / (ymax - ymin)) * (bottom - top);
    g.font = "10px system-ui";
    g.lineWidth = 1;
    for (let i = 0; i < 5; i++) {
      const t = i / 4,
        x = left + (right - left) * t,
        y = top + (bottom - top) * t;
      g.strokeStyle = "#243145";
      g.beginPath();
      g.moveTo(left, y);
      g.lineTo(right, y);
      g.stroke();
      g.fillStyle = "#93a7be";
      g.textAlign = "right";
      g.fillText((ymax - (ymax - ymin) * t).toPrecision(3), left - 9, y + 3);
      g.textAlign = "center";
      g.fillText((xmin + (xmax - xmin) * t).toPrecision(3), x, bottom + 17);
    }
    g.fillStyle = "#93a7be";
    g.textAlign = "center";
    g.fillText(this.labels[0], (left + right) / 2, h - 4);
    g.save();
    g.beginPath();
    g.rect(left, top, right - left, bottom - top);
    g.clip();
    for (const s of finiteSeries) {
      g.strokeStyle = s.color;
      g.fillStyle = s.color;
      g.lineWidth = s.width || 1.5;
      g.setLineDash(s.dash ? [4, 4] : []);
      g.beginPath();
      let started = false;
      for (let i = 0; i < s.x.length; i++) {
        const x = X(s.x[i]),
          y = Y(s.y[i]);
        if (!Number.isFinite(x + y)) {
          started = false;
          continue;
        }
        if (s.points) {
          if (s.x.length < 2500) {
            g.moveTo(x + 1.4, y);
            g.arc(x, y, 1.4, 0, Math.PI * 2);
          } else {
            if (!started) g.moveTo(x, y);
            else g.lineTo(x, y);
            started = true;
          }
        } else {
          if (!started) g.moveTo(x, y);
          else g.lineTo(x, y);
          started = true;
        }
      }
      if (s.points && s.x.length < 2500) g.fill();
      else g.stroke();
    }
    g.restore();
  }
}
const spectrum = new Plot("spectrum"),
  residuals = new Plot("residuals"),
  trend = new Plot("trend");
function paramsTable() {
  const root = $("parameters");
  root.replaceChildren();
  const items = [
    ["offset", config.model.offset],
    ...config.model.components.flatMap((c) =>
      Object.entries(c.parameters).map(([k, v]) => [c.prefix + "." + k, v]),
    ),
  ];
  for (const [name, p0] of items) {
    const p =
      typeof p0 === "number"
        ? { value: p0, min: null, max: null, fixed: false }
        : p0;
    const tr = document.createElement("tr"),
      td = document.createElement("td");
    td.textContent = name;
    td.title = name;
    tr.append(td);
    for (const field of ["value", "min", "max", "fixed"]) {
      const cell = document.createElement("td"),
        input = document.createElement("input");
      input.type = field === "fixed" ? "checkbox" : "number";
      input.step = "any";
      input.setAttribute("aria-label", name + " " + field);
      if (field === "fixed") input.checked = !!p[field];
      else input.value = p[field] ?? "";
      input.addEventListener("change", () => {
        p[field] =
          field === "fixed"
            ? input.checked
            : input.value === ""
              ? null
              : Number(input.value);
      });
      cell.append(input);
      tr.append(cell);
    }
    root.append(tr);
  }
}
function loadForm(c) {
  config = { ...clone(metadata.default_config), ...clone(c) };
  const parameter = (p) =>
    typeof p === "number"
      ? { value: p, min: null, max: null, fixed: false }
      : p;
  config.model.offset = parameter(config.model.offset ?? 0);
  for (const component of config.model.components) {
    component.parameters = Object.fromEntries(
      Object.entries(component.parameters || {}).map(([k, v]) => [
        k,
        parameter(v),
      ]),
    );
  }
  const components = config.model.components;
  if (
    components.length &&
    components.every((c) => c.kind === components[0].kind)
  ) {
    $("kind").value = components[0].kind;
    $("count").value = components.length;
  } else if (
    components.length &&
    components.every((c) =>
      ["asymmetric_gaussian", "gaussian_step"].includes(c.kind),
    )
  ) {
    $("kind").value = "nexafs";
    $("count").value = components.filter(
      (c) => c.kind === "asymmetric_gaussian",
    ).length;
    $("steps").value = components.filter(
      (c) => c.kind === "gaussian_step",
    ).length;
  }
  paramsTable();
  const s = config.source;
  $("source-mode").value = s.mode;
  $("path").value = s.path || "";
  $("expected").value = s.expected_points || "";
  $("glob").value = s.glob || "*.csv";
  $("columns").value = JSON.stringify(s.columns || { x: 0, y: 1 });
  $("delimiter").value = s.delimiter || "auto";
  $("header-row").checked = !!s.header;
  $("background").value = config.background.kind || "none";
  $("budget").value = config.fit.budget_seconds || 2;
  $("low").value = config.fit.interval?.[0] ?? "";
  $("high").value = config.fit.interval?.[1] ?? "";
  $("x-unit").value = config.units.x;
  $("y-unit").value = config.units.y;
  $("advanced").value = JSON.stringify(config, null, 2);
  sourceHelp();
}
function sourceHelp() {
  $("source-help").textContent =
    $("source-mode").value === "tail"
      ? "Set points per scan, a scan_id column, or write # scan_id=… / # end markers. Pauses do not complete a scan."
      : $("source-mode").value === "directory"
        ? "Publish immutable files by atomic rename (.part → .csv), or configure done_suffix in advanced JSON. Every file receives a result."
        : "The simulator alternates growing and complete spectra, with small peak drift and noise.";
}
function readForm() {
  const c = clone(config);
  c.source.mode = $("source-mode").value;
  c.source.columns = JSON.parse($("columns").value);
  c.source.delimiter = $("delimiter").value;
  c.source.header = $("header-row").checked;
  if (c.source.mode !== "demo") {
    c.source.path = $("path").value;
    c.source.glob = $("glob").value;
  }
  if ($("expected").value)
    c.source.expected_points = Number($("expected").value);
  else delete c.source.expected_points;
  c.background.kind = $("background").value;
  c.fit.budget_seconds = Number($("budget").value);
  if ($("low").value !== "" || $("high").value !== "") {
    if ($("low").value === "" || $("high").value === "")
      throw Error("Enter both interval endpoints");
    c.fit.interval = [Number($("low").value), Number($("high").value)];
  } else delete c.fit.interval;
  c.units = { x: $("x-unit").value, y: $("y-unit").value };
  return c;
}
async function apply(c) {
  $("error").hidden = true;
  await api("/v1/config", c);
  loadForm(c);
  spectrum.view = null;
  residuals.view = null;
}
function render(s) {
  state = s;
  $("version").textContent = s.version;
  $("connection").textContent = s.paused ? "Paused" : "Live · local";
  $("pause").textContent = s.paused
    ? "Resume acquisition"
    : "Pause acquisition";
  const latest = s.latest,
    r = latest?.result,
    display = r?.success ? latest : s.last_success,
    good = display?.result;
  $("scan").textContent = s.data?.scan_id || "Waiting";
  const statusLabels = {
    converged: "Converged",
    awaiting_coverage: "Waiting for peak coverage",
    singular: "Parameters not identifiable",
    timeout: "Fit time limit",
    max_evaluations: "Fit work limit",
    invalid: "Invalid scan",
    insufficient_data: "Not enough data",
  };
  $("status").textContent = latest
    ? (latest.complete ? "Completed · " : "Provisional · ") +
      (statusLabels[latest.status] || latest.status)
    : "Waiting for points";
  $("timing").textContent = r
    ? (r.elapsed_seconds * 1000).toFixed(0) + " ms"
    : "—";
  $("backlog").textContent = s.queue_depth + s.source_backlog;
  $("message").textContent =
    (latest?.error || r?.message || s.notice) +
    (latest
      ? " · revision " +
        s.revision +
        " · lag " +
        latest.lag_seconds.toFixed(2) +
        " s"
      : "");
  $("export-path").textContent = s.output_dir || "Disabled";
  const curves = [];
  if (s.data)
    curves.push({ x: s.data.x, y: s.data.y, color: "#9aaec5", points: true });
  if (good) {
    curves.push(
      { x: good.x, y: good.fitted, color: "#59e0c5", width: 2.2 },
      { x: good.x, y: good.background, color: "#e6be78", dash: true },
    );
    let i = 0;
    for (const [k, v] of Object.entries(good.components))
      if (k !== "offset")
        curves.push({
          x: good.x,
          y: v.map(
            (y, j) =>
              y + good.background[j] + (good.components.offset?.[j] || 0),
          ),
          color: palette[i++ % palette.length],
          dash: true,
        });
    $("spectrum-note").textContent =
      "Fit: " +
      display.scan_id +
      (display.complete ? " · completed" : " · provisional") +
      (display !== latest ? " · last successful" : "");
    residuals.set(
      [{ x: good.x, y: good.residuals, color: "#7ca9ff" }],
      [s.config.units.x, "residual"],
    );
    const root = $("results");
    root.replaceChildren();
    for (const [k, v] of Object.entries(good.parameters)) {
      const tr = document.createElement("tr");
      for (const text of [k, number(v), number(good.stderr[k])]) {
        const td = document.createElement("td");
        td.textContent = text;
        tr.append(td);
      }
      root.append(tr);
    }
    $("result-note").textContent =
      "rank " + good.rank + " · " + good.dof + " degrees of freedom";
    const choice = $("trend-parameter");
    const selected =
      choice.value ||
      Object.keys(good.parameters).find((k) => k.endsWith(".center")) ||
      "offset";
    if (
      [...choice.options].map((o) => o.value).join("|") !==
      Object.keys(good.parameters).join("|")
    ) {
      choice.replaceChildren(
        ...Object.keys(good.parameters).map((k) => new Option(k, k)),
      );
      choice.value = selected;
    }
  } else {
    residuals.set([], [s.config.units.x, "residual"]);
    $("results").replaceChildren();
    $("result-note").textContent = "";
    $("spectrum-note").textContent = "Waiting for a fit with the current setup";
  }
  spectrum.set(curves, [s.config.units.x, s.config.units.y]);
  renderTrend();
}
function renderTrend() {
  if (!state) return;
  const key = $("trend-parameter").value;
  const h = state.history.filter(
    (r) => r.status === "converged" && Number.isFinite(r.parameters[key]),
  );
  trend.set(
    [
      {
        x: h.map((r) => r.sequence),
        y: h.map((r) => r.parameters[key]),
        color: "#59e0c5",
        points: true,
      },
    ],
    ["fit update", key],
  );
}
function action(id, fn) {
  $(id).addEventListener("click", async () => {
    const b = $(id);
    b.disabled = true;
    try {
      await fn();
    } catch (e) {
      error(e);
    } finally {
      b.disabled = false;
    }
  });
}
action("build-model", () => {
  const kind = $("kind").value,
    n = Number($("count").value),
    steps = Number($("steps").value);
  if (
    !Number.isInteger(n) ||
    n < 1 ||
    n > 20 ||
    !Number.isInteger(steps) ||
    steps < 0 ||
    steps > 20
  )
    throw Error("Choose 1–20 peaks and 0–20 steps");
  const kinds =
    kind === "nexafs"
      ? [
          ...Array(n).fill("asymmetric_gaussian"),
          ...Array(steps).fill("gaussian_step"),
        ]
      : Array(n).fill(kind);
  config.model = {
    offset: { value: 0.03, min: null, max: null, fixed: false },
    components: kinds.map((k, i) => ({
      kind: k,
      prefix: "p" + (i + 1),
      tail: "higher",
      parameters: Object.fromEntries(
        Object.entries(metadata.models[k]).map(([name, [v, min, max]]) => [
          name,
          {
            value:
              name === "center"
                ? kinds.length === 1
                  ? 0
                  : -1.5 + (3 * i) / (kinds.length - 1)
                : v,
            min,
            max,
            fixed: false,
          },
        ]),
      ),
    })),
  };
  paramsTable();
});
action("suggest", async () => {
  config.model = await api("/v1/suggest", { model: config.model });
  paramsTable();
});
action("apply", () => apply(readForm()));
action("apply-json", () => apply(JSON.parse($("advanced").value)));
action("pause", () =>
  api("/v1/control", { action: state?.paused ? "resume" : "pause" }),
);
action("save", () => {
  const c = readForm(),
    a = document.createElement("a");
  a.href = URL.createObjectURL(
    new Blob([JSON.stringify(c, null, 2) + "\n"], { type: "application/json" }),
  );
  a.download = "wavesfit-preset.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
});
action("load", () => $("file").click());
$("file").addEventListener("change", async (e) => {
  try {
    loadForm(JSON.parse(await e.target.files[0].text()));
  } catch (err) {
    error(err);
  }
});
$("source-mode").addEventListener("change", sourceHelp);
$("trend-parameter").addEventListener("change", renderTrend);
(async () => {
  metadata = await api("/v1/models");
  const s = await api("/v1/state");
  loadForm(s.config);
  render(s);
  const events = new EventSource("/v1/events");
  events.addEventListener("state", (e) => {
    try {
      render(JSON.parse(e.data));
    } catch (err) {
      error(err);
    }
  });
  events.onerror = () => {
    $("connection").textContent = "Reconnecting…";
  };
})().catch(error);
