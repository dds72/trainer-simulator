const endpoint = "/api/devices";
const serviceError = document.querySelector("#service-error");
const rates = [0.5, 1, 2, 4, 5, 10];

function showText(element, value) {
  if (element.textContent !== value) element.textContent = value;
}

function showError(element, message) {
  showText(element, message || "");
  element.hidden = !message;
}

class Panel {
  constructor(role, unit) {
    this.role = role;
    this.unit = unit;
    this.section = document.getElementById(role);
    this.controls = this.section.querySelector("fieldset");
    this.slider = this.section.querySelector("input[type=range]");
    this.power = this.section.querySelector("input[type=checkbox]");
    this.frequency = this.section.querySelector("select");
    this.status = this.section.querySelector(".status");
    this.error = this.section.querySelector(".device-error");
    this.output = this.section.querySelector("output");
    this.pending = new Map();
    this.revision = 0;
    this.saving = false;
    this.saveError = "";
    for (const rate of rates) this.frequency.add(new Option(`${rate} Hz`, rate));
    this.slider.addEventListener("input", () => {
      this.showReading(this.slider.value);
      this.update("reading", this.slider.valueAsNumber);
    });
    this.power.addEventListener("change", () => this.update("enabled", this.power.checked));
    this.frequency.addEventListener("change", () => this.update("rate", Number(this.frequency.value)));
  }

  showReading(reading) {
    const value = `${reading} ${this.unit}`;
    showText(this.output, value);
    this.slider.setAttribute("aria-valuetext", value);
  }

  render(state) {
    this.controls.disabled = false;
    this.power.checked = state.enabled;
    this.slider.value = state.reading;
    this.showReading(state.reading);
    this.frequency.value = state.rate;
    showText(this.status, state.status);
    this.status.dataset.state = state.status;
    const metrics = {
      actual_rate: `${state.actual_rate.toFixed(2)} Hz`,
      sent_count: String(state.sent_count),
      watts: state.watts === null ? "—" : `${state.watts} W`,
      target: state.target_watts !== null ? `ERG · ${state.target_watts} W` :
        state.target_resistance !== null ? `Resistance · ${state.target_resistance}` : "—",
    };
    for (const element of this.section.querySelectorAll("[data-metric]")) {
      showText(element, metrics[element.dataset.metric]);
    }
    showError(this.error, this.saveError || state.error);
  }

  async update(field, value) {
    this.revision++;
    this.pending.set(field, value);
    if (field === "enabled") this.power.disabled = true;
    if (this.saving) return;
    this.saving = true;
    this.saveError = "";
    let latest;
    while (this.pending.size) {
      const [key, setting] = this.pending.entries().next().value;
      this.pending.delete(key);
      try {
        const response = await fetch(`${endpoint}/${this.role}`, {
          method: "PATCH",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({[key]: setting}),
          signal: AbortSignal.timeout(8000),
        });
        if (!response.ok) throw new Error(await response.text());
        latest = await response.json();
      } catch (error) {
        this.saveError = error.message;
        showError(this.error, this.saveError);
      }
    }
    this.saving = false;
    if (latest) this.render(latest);
    this.power.disabled = false;
  }
}

const panels = {trainer: new Panel("trainer", "rpm"), hrm: new Panel("hrm", "bpm")};

async function refresh() {
  const revisions = Object.fromEntries(Object.entries(panels).map(([role, panel]) => [role, panel.revision]));
  try {
    const response = await fetch(endpoint, {cache: "no-store", signal: AbortSignal.timeout(2000)});
    if (!response.ok) throw new Error();
    const states = await response.json();
    showError(serviceError, "");
    for (const [role, panel] of Object.entries(panels)) {
      if (!panel.saving && panel.revision === revisions[role]) panel.render(states[role]);
    }
  } catch {
    showError(serviceError, "Simulator service unavailable. Start the service to restore controls.");
    for (const panel of Object.values(panels)) panel.controls.disabled = true;
  }
  setTimeout(refresh, 500);
}

refresh();
