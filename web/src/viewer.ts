// Interactive viewer for the campus digital twin.
// Reads window.TWIN_DATA (written by `python -m twin.build`) and draws the campus
// map for a chosen weekday and time: building occupancy as circles, road use in
// the current hour as line width. Compiled as a classic script so the viewer
// also works when index.html is opened straight from disk.

type Kind = "hall" | "academic" | "amenity" | "sports_open" | "gate";

interface Place {
  place: string;
  kind: Kind;
  x: number;
  y: number;
  capacity: number;
}

interface Segment {
  id: string;
  a: [number, number];
  b: [number, number];
}

interface TwinData {
  days: string[];
  times: string[];
  places: Place[];
  segments: Segment[];
  occupancy: Record<string, number[][]>; // day -> step -> place
  roads: Record<string, number[][]>; // day -> hour -> segment
  residents: number;
}

interface Window {
  TWIN_DATA: TwinData;
}

const KIND_COLOR: Record<Kind, string> = {
  hall: "#eb6834",
  academic: "#2a78d6",
  amenity: "#eda100",
  sports_open: "#008300",
  gate: "#52514e",
};
const KIND_LABEL: Record<Kind, string> = {
  hall: "Residential hall",
  academic: "Academic",
  amenity: "Amenity",
  sports_open: "Sports and open space",
  gate: "Gate",
};

const data = window.TWIN_DATA;
const state = { day: data.days[0], step: 12, playing: false };

const $ = <T extends HTMLElement>(id: string): T => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id}`);
  return el as T;
};

const canvas = $<HTMLCanvasElement>("map");
const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
const slider = $<HTMLInputElement>("time");
const tooltip = $<HTMLDivElement>("tooltip");

// ---------------------------------------------------------------- geometry
const xs = data.places.map((p) => p.x);
const ys = data.places.map((p) => p.y);
const bounds = { x0: Math.min(...xs) - 120, x1: Math.max(...xs) + 220, y0: Math.min(...ys) - 80, y1: Math.max(...ys) + 80 };
let scale = 1;
let offX = 0;
let offY = 0;

function resize(): void {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = bounds.x1 - bounds.x0;
  const h = bounds.y1 - bounds.y0;
  scale = Math.min(rect.width / w, rect.height / h);
  offX = (rect.width - w * scale) / 2;
  offY = (rect.height - h * scale) / 2;
}

const sx = (x: number): number => offX + (x - bounds.x0) * scale;
const sy = (y: number): number => offY + (bounds.y1 - y) * scale; // north up

const radius = (people: number): number => 3 + Math.sqrt(people) * 0.55 * scale * 1.6;

// ---------------------------------------------------------------- drawing
function currentHour(): number {
  return Math.floor(6 + state.step / 4);
}

function draw(): void {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  const occ = data.occupancy[state.day][state.step];
  const road = data.roads[state.day][currentHour()];
  const maxRoad = Math.max(1, ...data.days.flatMap((d) => data.roads[d].flat()));

  ctx.lineCap = "round";
  data.segments.forEach((s, i) => {
    ctx.strokeStyle = "#d9d8d3";
    ctx.lineWidth = 2;
    line(s);
    if (road[i] > 0) {
      ctx.strokeStyle = "rgba(42, 120, 214, 0.75)";
      ctx.lineWidth = 1.5 + 14 * (road[i] / maxRoad);
      line(s);
    }
  });

  data.places.forEach((p, i) => {
    const x = sx(p.x);
    const y = sy(p.y);
    if (p.capacity > 0) {
      ctx.beginPath();
      ctx.arc(x, y, radius(p.capacity), 0, Math.PI * 2);
      ctx.strokeStyle = "#c3c2b7";
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.beginPath();
    ctx.arc(x, y, Math.max(4, radius(occ[i])), 0, Math.PI * 2);
    ctx.fillStyle = KIND_COLOR[p.kind];
    ctx.globalAlpha = occ[i] > 0 ? 0.85 : 0.35;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    ctx.fillStyle = "#0b0b0b";
    ctx.font = "11px Inter, system-ui, sans-serif";
    ctx.fillText(p.place, x + Math.max(6, radius(p.capacity)) + 3, y + 4);
  });
}

function line(s: Segment): void {
  ctx.beginPath();
  ctx.moveTo(sx(s.a[0]), sy(s.a[1]));
  ctx.lineTo(sx(s.b[0]), sy(s.b[1]));
  ctx.stroke();
}

// ---------------------------------------------------------------- side panel
function fmt(n: number): string {
  return Math.round(n).toLocaleString("en-IN");
}

function updatePanel(): void {
  const occ = data.occupancy[state.day][state.step];
  const road = data.roads[state.day][currentHour()];
  $("clock").textContent = `${state.day} ${data.times[state.step]}`;

  const inHalls = data.places.reduce((sum, p, i) => sum + (p.kind === "hall" ? occ[i] : 0), 0);
  $("stat-away").textContent = fmt(data.residents - inHalls);
  $("stat-halls").textContent = fmt(inHalls);
  $("stat-trips").textContent = fmt(road.reduce((a, b) => a + b, 0));

  const busiest = data.places
    .map((p, i) => ({ p, people: occ[i] }))
    .filter((r) => r.p.kind !== "hall" && r.p.capacity > 0 && r.people > 0)
    .sort((a, b) => b.people / b.p.capacity - a.people / a.p.capacity)
    .slice(0, 6);
  $("busiest").innerHTML = busiest.length
    ? busiest
        .map((r) => {
          const pct = Math.round((100 * r.people) / r.p.capacity);
          return `<li><span class="name">${r.p.place}</span><span class="bar"><i style="width:${Math.min(100, pct)}%;background:${KIND_COLOR[r.p.kind]}"></i></span><span class="val">${pct}%</span></li>`;
        })
        .join("")
    : `<li class="empty">Campus buildings are empty at this time.</li>`;

  const roads = data.segments
    .map((s, i) => ({ s, n: road[i] }))
    .filter((r) => r.n > 0)
    .sort((a, b) => b.n - a.n)
    .slice(0, 5);
  $("roads").innerHTML = roads.length
    ? roads.map((r) => `<li><span class="name">${r.s.id.replace("--", " – ")}</span><span class="val">${fmt(r.n)}</span></li>`).join("")
    : `<li class="empty">No trips in this hour.</li>`;
}

function render(): void {
  slider.value = String(state.step);
  document.querySelectorAll<HTMLButtonElement>("#days button").forEach((b) => {
    b.classList.toggle("active", b.dataset.day === state.day);
  });
  draw();
  updatePanel();
}

// ---------------------------------------------------------------- interaction
function hitTest(mx: number, my: number): number {
  const occ = data.occupancy[state.day][state.step];
  for (let i = data.places.length - 1; i >= 0; i--) {
    const p = data.places[i];
    const r = Math.max(8, radius(occ[i]));
    if (Math.hypot(mx - sx(p.x), my - sy(p.y)) <= r) return i;
  }
  return -1;
}

canvas.addEventListener("mousemove", (e) => {
  const rect = canvas.getBoundingClientRect();
  const i = hitTest(e.clientX - rect.left, e.clientY - rect.top);
  if (i < 0) {
    tooltip.hidden = true;
    return;
  }
  const p = data.places[i];
  const people = data.occupancy[state.day][state.step][i];
  const util = p.capacity > 0 ? ` · ${Math.round((100 * people) / p.capacity)}% of ${fmt(p.capacity)}` : "";
  tooltip.innerHTML = `<b>${p.place}</b><br>${KIND_LABEL[p.kind]}<br>${fmt(people)} people${util}`;
  tooltip.style.left = `${e.clientX - rect.left + 14}px`;
  tooltip.style.top = `${e.clientY - rect.top + 14}px`;
  tooltip.hidden = false;
});
canvas.addEventListener("mouseleave", () => (tooltip.hidden = true));

slider.max = String(data.times.length - 1);
slider.addEventListener("input", () => {
  state.step = Number(slider.value);
  render();
});

$("days").innerHTML = data.days.map((d) => `<button data-day="${d}">${d}</button>`).join("");
$("days").addEventListener("click", (e) => {
  const day = (e.target as HTMLElement).dataset.day;
  if (day) {
    state.day = day;
    render();
  }
});

let timer: number | undefined;
$("play").addEventListener("click", () => {
  state.playing = !state.playing;
  $("play").textContent = state.playing ? "Pause" : "Play";
  if (state.playing) {
    timer = window.setInterval(() => {
      state.step = (state.step + 1) % data.times.length;
      render();
    }, 350);
  } else {
    window.clearInterval(timer);
  }
});

$("legend").innerHTML = (Object.keys(KIND_COLOR) as Kind[])
  .map((k) => `<span><i style="background:${KIND_COLOR[k]}"></i>${KIND_LABEL[k]}</span>`)
  .join("");

window.addEventListener("resize", () => {
  resize();
  render();
});
resize();
render();

