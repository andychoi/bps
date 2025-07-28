---

### `bps/_action_reset.html`
```html
<button class="btn btn-sm btn-danger" onclick="resetData()">
  🔄 Reset All
</button>
<script>
function resetData() {
  if (!confirm("This will zero out all existing values before saving. Continue?")) return;
  fetch("/api/bps_planning_grid_update", {
    method: "PATCH",
    headers: {
      "Content-Type":"application/json",
      "X-CSRFToken":"{{ csrf_token }}"
    },
    body: JSON.stringify({
      layout:   {{ layout.id }},
      action_type: "RESET",
      updates: []  // no individual cells needed, reset happens before manual edits
    })
  }).then(_=>{
    table.replaceData();  // reload the grid
    alert("All values have been reset to zero.");
  });
}
</script>
```

### `bps/_tabulator.html`
```html
{# templates/bps/_tabulator.html #}
<link
  rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/tabulator-tables@6.2.1/dist/css/tabulator_bootstrap5.min.css"
/>
<div
  id="tabulator-app"
  data-api-url="{{ api_url }}"
  data-detail-tmpl="{{ detail_url }}"
  data-change-tmpl="{{ change_url }}"
  data-create-url="{{ create_url }}"
  data-export-url="{{ export_url }}"
  data-owner-update-tmpl="{{ owner_update_url }}"
  data-orgunit-update-tmpl="{{ orgunit_update_url }}"
  data-user-autocomplete-url="{{ user_ac_url }}"
  data-orgunit-autocomplete-url="{{ orgunit_ac_url }}"
></div>
<script src="https://cdn.jsdelivr.net/npm/vue@3/dist/vue.global.prod.js"></script>
<script src="https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/tabulator-tables@6.3/dist/js/tabulator.min.js"></script>
<script>
// --- CSRF helper ---
function getCookie(name) {
  let v = null;
  document.cookie.split(';').forEach(c => {
    c = c.trim();
    if (c.startsWith(name + '=')) {
      v = decodeURIComponent(c.slice(name.length + 1));
    }
  });
  return v;
}
const csrftoken = getCookie("csrftoken");
// --- style for editable cells ---
const style = document.createElement("style");
style.innerHTML = `
  .tabulator-cell.editable-cell {
    background-color: #fff8dc !important;
  }
`;
document.head.appendChild(style);
// --- generic autocomplete editor factory ---
function makeAutocompleteEditor(endpoint) {
  return function(cell, onRendered, success, cancel) {
    const input = document.createElement("input");
    input.type = "search";
    input.placeholder = "Search…";
    input.value = cell.getValue()?.display || "";
    Object.assign(input.style, {
      padding: "4px",
      width: "100%",
      boxSizing: "border-box"
    });
    onRendered(() => input.focus());
    let list;
    const lookup = async term => {
      const res = await axios.get(endpoint, {
        params: { q: term },
        withCredentials: true,
        headers: { "X-CSRFToken": csrftoken }
      });
      return res.data.results.map(u => ({
        label: u.text,
        value: u.id
      }));
    };
    const showList = async () => {
      const items = await lookup(input.value);
      if (list) list.remove();
      list = document.createElement("div");
      list.className = "list-group";
      Object.assign(list.style, {
        position: "absolute",
        zIndex: 10000,
        maxHeight: "150px",
        overflowY: "auto"
      });
      items.forEach(it => {
        const a = document.createElement("a");
        a.className = "list-group-item list-group-item-action";
        a.innerText = it.label;
        a.onclick = () => {
          success({ id: it.value, display: it.label });
          list.remove();
        };
        list.appendChild(a);
      });
      document.body.appendChild(list);
      const r = input.getBoundingClientRect();
      list.style.top = `${r.bottom}px`;
      list.style.left = `${r.left}px`;
      document.addEventListener("click", () => list.remove(), {
        once: true
      });
    };
    input.addEventListener("input", showList);
    input.addEventListener("blur", () => setTimeout(cancel, 150));
    return input;
  };
}
// --- mount Tabulator inside Vue ---
const { createApp, onMounted } = Vue;
createApp({
  setup() {
    const el = document.getElementById("tabulator-app");
    // pull in the data-attributes
    const API        = el.dataset.apiUrl;
    const DETAIL_TPL = el.dataset.detailTmpl;
    const CHANGE_TPL = el.dataset.changeTmpl;
    const CREATE_URL = el.dataset.createUrl;
    const EXPORT_URL = el.dataset.exportUrl;
    const OWNER_TPL  = el.dataset.ownerUpdateTmpl;
    const OU_TPL     = el.dataset.orgunitUpdateTmpl;
    const USER_AC    = el.dataset.userAutocompleteUrl;
    const OU_AC      = el.dataset.orgunitAutocompleteUrl;
    // simple helper to replace the placeholder "0" in e.g. ".../0/" with a real id
    function makeUrl(tmpl, id) {
      return tmpl.replace(/\/0\//, `/${id}/`);
    }
    const userEditor    = makeAutocompleteEditor(USER_AC);
    const orgunitEditor = makeAutocompleteEditor(OU_AC);
    onMounted(() => {
      el.innerHTML = `
<div class="container-fluid mt-2">
  <div class="d-flex justify-content-between mb-3">
    <h4>Planning Data</h4>
    <div class="btn-toolbar">
      <input id="grid-search" class="form-control me-2" placeholder="Search…">
      <button id="btn-add" class="btn btn-primary me-2">
        <i class="bi bi-plus-lg"></i> Add
      </button>
      <button id="btn-export" class="btn btn-secondary">
        <i class="bi bi-download"></i> Export
      </button>
    </div>
  </div>
  <div id="grid-table"></div>
</div>`;
      const table = new Tabulator("#grid-table", {
        layout: "fitDataStretch",
        ajaxURL: API,
        ajaxConfig: { credentials: "include" },
        pagination: "remote",
        paginationSize: 20,
        paginationDataSent: { page: "page", size: "page_size" },
        paginationDataReceived: { last_page: "last_page" },
        ajaxResponse: (url, params, res) => ({
          data: res.results,
          last_page: Math.ceil(res.count / params.size)
        }),
        columns: [
          { title: "#", formatter: "rownum", width: 50 },
          {
            title: "Org Unit",
            field: "org_unit",
            formatter: cell => cell.getValue()?.display || ""
          },
          {
            title: "Service",
            field: "service",
            formatter: cell => cell.getValue()?.display || ""
          },
          { title: "Key Figure", field: "key_figure" },
          {
            title: "Value",
            field: "value",
            editor: "input",
            cellEdited: cell => {
              const d = cell.getRow().getData();
              axios
                .patch(
                  makeUrl(CHANGE_TPL, d.id),
                  { [cell.getField()]: cell.getValue() },
                  {
                    withCredentials: true,
                    headers: { "X-CSRFToken": csrftoken }
                  }
                )
                .catch(() => cell.restoreOldValue());
            }
          }
        ]
      });
      // wire up search
      document
        .getElementById("grid-search")
        .addEventListener("input", e => {
          table.setFilter("service", "like", e.target.value);
          table.setPage(1);
        });
      // "Add" goes straight to your create-URL
      document
        .getElementById("btn-add")
        .addEventListener("click", () => (window.location = CREATE_URL));
      // Export CSV
      document
        .getElementById("btn-export")
        .addEventListener("click", () =>
          table.download("csv", "planning_export.csv")
        );
    });
  }
}).mount("#tabulator-app");
</script>
```

### `bps/base.html`
```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Enterprise Planning{% endblock %}</title>
    <link href="{% static 'css/bootstrap.min.css' %}" rel="stylesheet">
    <link href="{% static 'css/bootstrap-icons.css' %}" rel="stylesheet">
    <link href="{% static 'css/custom.css' %}" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-light shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand" href="{% url 'bps:dashboard' %}">CorpPlanner</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarMain" aria-controls="navbarMain" aria-expanded="false" aria-label="Toggle navigation">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarMain">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    {% block nav_links %}
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'bps:inbox' %}"><i class="bi bi-inbox"></i> Inbox</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{% url 'bps:notifications' %}"><i class="bi bi-bell"></i> Notifications</a>
                    </li>
                    {% endblock %}
                </ul>
                <ul class="navbar-nav ms-auto mb-2 mb-lg-0">
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="userDropdown" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                            <i class="bi bi-person-circle"></i> {{ request.user.get_full_name }}
                        </a>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                            <li><a class="dropdown-item" href="{% url 'bps:profile' %}">Profile</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="{% url 'logout' %}">Logout</a></li>
                        </ul>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    <div class="container-fluid mt-3">
        {% if breadcrumbs %}
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                {% for crumb in breadcrumbs %}
                <li class="breadcrumb-item {% if forloop.last %}active{% endif %}" {% if forloop.last %}aria-current="page"{% endif %}>
                    {% if not forloop.last %}
                    <a href="{{ crumb.url }}">{{ crumb.title }}</a>
                    {% else %}
                    {{ crumb.title }}
                    {% endif %}
                </li>
                {% endfor %}
            </ol>
        </nav>
        {% endif %}
        {% if messages %}
            {% for message in messages %}
            <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
            {% endfor %}
        {% endif %}
        {% block content %}{% endblock %}
    </div>
    <script src="{% static 'js/bootstrap.bundle.min.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### `bps/constant_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Constants</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Value</th></tr></thead>
  <tbody>
    {% for c in consts %}
      <tr><td>{{ c.name }}</td><td>{{ c.value }}</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `bps/dashboard.html`
```html
{% extends "bps/base.html" %}
{% load static %}
{% block content %}
<div class="container py-4">
  <h1 class="mb-4">Planning Dashboard</h1>
  <div class="row mb-4">
    <div class="col-md-4">
      <div class="card">
        <div class="card-header">Select Planning Year</div>
        <div class="card-body p-3">
          <form method="get">
            <select name="year" class="form-select" onchange="this.form.submit()">
              {% for y in all_years %}
                <option value="{{ y }}" {% if y == selected_year %}selected{% endif %}>
                  {{ y }}
                </option>
              {% endfor %}
            </select>
          </form>
        </div>
      </div>
    </div>
  </div>
  <div class="row gy-4">
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-header bg-warning text-white">Incomplete Planning Tasks</div>
        <ul class="list-group list-group-flush">
          {% for sess in incomplete_sessions %}
            <li class="list-group-item">
              <a href="{% url 'bps:session_detail' sess.pk %}">
                {{ sess.org_unit.name }} &dash; {{ sess.layout_year.layout.name }}
              </a>
            </li>
          {% empty %}
            <li class="list-group-item">None—everything is up to date!</li>
          {% endfor %}
        </ul>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card h-100">
        <div class="card-header bg-info text-white">Available Layouts</div>
        <div class="card-body">
          <div class="row row-cols-1 row-cols-md-2 g-3">
            {% for ly in layouts %}
              <div class="col">
                <div class="card h-100">
                  <div class="card-body p-2">
                    <h5 class="card-title mb-1">{{ ly.layout.title }}</h5>
                    <p class="card-text small mb-0">Version: {{ ly.version.code }}</p>
                  </div>
                  <div class="card-footer text-end">
                    <a href="{% url 'bps:session_list' %}?layout_year={{ ly.pk }}"
                       class="btn btn-sm btn-outline-primary">
                       Open
                    </a>
                  </div>
                </div>
              </div>
            {% empty %}
              <p class="text-muted">No layouts defined for {{ selected_year }}.</p>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header bg-success text-white">Planning Functions</div>
        <div class="card-body">
          <div class="list-group">
            <a href="{ url 'bps:manual-planning-select' }" class="list-group-item list-group-item-action">
              🧮 Manual Planning Grid
            </a>
            {% for fn in planning_funcs %}
              <a href="{{ fn.url }}" class="list-group-item list-group-item-action">
                {{ fn.name }}
              </a>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
    <div class="col-md-6">
      <div class="card">
        <div class="card-header bg-secondary text-white">Admin</div>
        <div class="card-body">
          <div class="list-group">
            {% for link in admin_links %}
              <a href="{{ link.url }}" class="list-group-item list-group-item-action">
                {{ link.name }}
              </a>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### `bps/data_request_detail.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Data Request {{ dr.id }}</h1>
  <form method="post" class="mb-4">{% csrf_token %}
    {{ form|crispy }}
    <button type="submit" class="btn btn-primary">Update</button>
    <a href="{% url 'bps:data_request_list' %}" class="btn btn-link">Back to list</a>
  </form>
  <h2>Facts</h2>
  <table class="table table-striped">
    <thead>
      <tr>
        <th>Period</th>
        <th>Qty</th>
        <th>UoM</th>
        <th>Amount</th>
        <th>UoM</th>
        <th>Other</th>
        <th>Value</th>
      </tr>
    </thead>
    <tbody>
      {% for f in facts %}
      <tr>
        <td>{{ f.period }}</td>
        <td>{{ f.quantity }}</td>
        <td>{{ f.quantity_uom }}</td>
        <td>{{ f.amount }}</td>
        <td>{{ f.amount_uom }}</td>
        <td>{{ f.other_key_figure }}</td>
        <td>{{ f.other_value }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7">No facts recorded yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
  <a href="{% url 'bps:fact_list' dr.pk %}" class="btn btn-success">Add/Edit Facts</a>
</div>
{% endblock %}
```

### `bps/data_request_list.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Data Requests</h1>
  <ul class="list-group mt-3">
    {% for dr in data_requests %}
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <a href="{% url 'bps:data_request_detail' dr.pk %}">
          {{ dr.id }} – {{ dr.description|default:"(no description)" }}
        </a>
        <span class="badge bg-secondary">
          {{ dr.created_at|date:"Y-m-d H:i" }}
        </span>
      </li>
    {% empty %}
      <li class="list-group-item">No data requests found.</li>
    {% endfor %}
  </ul>
</div>
{% endblock %}
```

### `bps/fact_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Facts for Request {{ dr.id }}</h1>
  <form method="post" class="row g-3 align-items-end mb-4">{% csrf_token %}
    <div class="col-md-2">
      {{ form.session|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.period|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.quantity|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.quantity_uom|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.amount|as_crispy_field }}
    </div>
    <div class="col-md-2">
      {{ form.amount_uom|as_crispy_field }}
    </div>
    <div class="col-md-3">
      {{ form.other_key_figure|as_crispy_field }}
    </div>
    <div class="col-md-3">
      {{ form.other_value|as_crispy_field }}
    </div>
    <div class="col-md-2">
      <button type="submit" class="btn btn-primary">Save Fact</button>
      <a href="{% url 'bps:data_request_detail' dr.pk %}" class="btn btn-link">Done</a>
    </div>
  </form>
  <table class="table table-bordered">
    <thead>
      <tr>
        <th>Period</th><th>Qty</th><th>UoM</th>
        <th>Amount</th><th>UoM</th><th>Other</th><th>Value</th>
      </tr>
    </thead>
    <tbody>
      {% for f in facts %}
      <tr>
        <td>{{ f.period }}</td>
        <td>{{ f.quantity }}</td>
        <td>{{ f.quantity_uom }}</td>
        <td>{{ f.amount }}</td>
        <td>{{ f.amount_uom }}</td>
        <td>{{ f.other_key_figure }}</td>
        <td>{{ f.other_value }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7">No facts yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `bps/formula_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Formulas</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Loop Dim</th><th>Expression</th><th>Actions</th></tr></thead>
  <tbody>
    {% for f in formulas %}
      <tr>
        <td>{{ f.name }}</td>
        <td>{{ f.loop_dimension.model }}</td>
        <td><code>{{ f.expression }}</code></td>
        <td>
          <a href="{% url 'formula_run' f.pk %}?period=01" class="btn btn-sm btn-primary">
            Run
          </a>
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `bps/inbox.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Inbox</h1>
  <p class="text-muted">(Nothing to show yet.)</p>
  {# Replace with a list of actionable items when you wire it up #}
</div>
{% endblock %}
```

### `bps/manual_planning.html`
```html
{# bps/manual_planning.html #}
{% extends 'bps/base.html' %}
{% load static %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>Manual Planning: {{ layout_year.layout.name }} | {{ layout_year.year.code }} / {{ layout_year.version.code }}</h2>
  <div>
    <button class="btn btn-success" onclick="saveGrid()">Save</button>
    <button class="btn btn-secondary" onclick="revertGrid()">Revert</button>
  </div>
</div>
<div id="planning-grid"></div>
{% endblock %}
{% block extra_js %}
<link href="https://unpkg.com/tabulator-tables@6.3.0/dist/css/tabulator.min.css" rel="stylesheet">
<script src="https://unpkg.com/tabulator-tables@6.3.0/dist/js/tabulator.min.js"></script>
<script>
const layout = {{ layout_year.id }};
const year   = {{ layout_year.year.id }};
const version= "{{ layout_year.version.code }}";
let changed = [];
const table = new Tabulator('#planning-grid', {
  layout: 'fitDataStretch',
  ajaxURL: `/api/planning-grid/?layout=${layout}&year=${year}&version=${version}`,
  ajaxResponse: (url, _, data) => data,
  columns: [{ title:'Cost Center', field:'cost_center', frozen:true, headerFilter:'input' },
            { title:'Service', field:'service', frozen:true },
            { title:'Key Figure', field:'key_figure' },
    {% for p in periods %}
    { title:'{{ p.name }}', field:'M{{ p.code }}', editor:'number', bottomCalc:'sum' },
    {% endfor %}
  ],
  cellEdited: (cell) => changed.push({id:cell.getData().id,field:cell.getField(),value:cell.getValue()}),
});
function saveGrid() {
  if (!changed.length) return alert('No changes');
  fetch('/api/planning-grid/', {
    method: 'POST',
    headers: {'Content-Type':'application/json','X-CSRFToken':'{{ csrf_token }}'},
    body: JSON.stringify({layout,updates:changed})
  }).then(r=>r.ok?location.reload():alert('Save failed'));
}
function revertGrid() { changed=[]; table.replaceData(); }
</script>
{% endblock %}
```

### `bps/manual_planning_select.html`
```html
{# manual_planning_select.html #}
{% extends "bps/base.html" %}
{% block content %}
<h2>Select Manual Planning</h2>
<form id="select-form">
  <div class="mb-3">
    <label for="layout" class="form-label">Layout/Year/Version</label>
    <select id="layout" class="form-select">
      {% for ly in layouts %}
      <option value="{{ ly.layout.id }}|{{ ly.year.id }}|{{ ly.version.id }}">
        {{ ly.layout.name }} - {{ ly.year.code }}/{{ ly.version.code }}
      </option>
      {% endfor %}
    </select>
  </div>
  <button class="btn btn-primary">Launch</button>
</form>
<script>
  document.getElementById('select-form').addEventListener('submit', e=>{
    e.preventDefault();
    let [l,y,v] = document.getElementById('layout').value.split('|');
    window.location.href = `{% url 'bps:manual-planning' 0 0 0 %}`
      .replace('/0/0/0/', `/${l}/${y}/${v}/`);
  });
</script>
{% endblock %}
```

### `bps/notifications.html`
```html
{% extends "bps/base.html" %}
{% block content %}
<div class="container my-4">
  <h1>Notifications</h1>
  <p class="text-muted">You have no new notifications.</p>
  {# Replace with real notification stream when ready #}
</div>
{% endblock %}
```

### `bps/planning_function_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Planning Functions</h1>
  <form method="post" class="mb-4">{% csrf_token %}
    {{ form|crispy }}
  </form>
  <table class="table table-striped">
    <thead>
      <tr>
        <th>Name</th>
        <th>Layout</th>
        <th>Type</th>
        <th>Parameters (JSON)</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for fn in functions %}
      <tr>
        <td>{{ fn.name }}</td>
        <td>{{ fn.layout.code }}</td>
        <td>{{ fn.get_function_type_display }}</td>
        <td><code>{{ fn.parameters }}</code></td>
        <td>
          <a href="{% url 'bps:run_function' fn.pk sess_id=fn.pk %}" class="btn btn-sm btn-primary">
            Run
          </a>
        </td>
      </tr>
      {% empty %}
      <tr><td colspan="5">No planning functions defined.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `bps/reference_data_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Reference Data</h1>
  <form method="post" class="mb-4">{% csrf_token %}
    {{ form|crispy }}
  </form>
  <table class="table table-hover">
    <thead>
      <tr>
        <th>Name</th>
        <th>Version</th>
        <th>Year</th>
        <th>Description</th>
      </tr>
    </thead>
    <tbody>
      {% for ref in references %}
      <tr>
        <td>{{ ref.name }}</td>
        <td>{{ ref.source_version.code }}</td>
        <td>{{ ref.source_year.code }}</td>
        <td>{{ ref.description|default:"–" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4">No reference data found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

### `bps/session_detail.html`
```html
{# templates/bps/session_detail.html #}
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block extra_head %}
  {# needed only for your Period table below #}
  <script src="https://unpkg.com/vue@3"></script>
{% endblock %}
{% block content %}
  <h1>Planning: {{ sess.org_unit.name }} / {{ sess.layout_year }}</h1>
  {# — Start Session — #}
  {% if can_edit %}
    <form method="post" class="mb-3">{% csrf_token %}
      {{ form|crispy }}
    </form>
  {% endif %}
  {# — Period Definition — #}
  <h2>Period Definition</h2>
  <form method="post" class="mb-3">{% csrf_token %}
    {{ period_form|crispy }}
  </form>
  <div id="period-table">
    <vue-period-table :buckets="{{ periods|safe }}" />
  </div>
    <h2>Raw Facts ({{ dr.description }})</h2>
  <table class="table table-striped table-bordered">
    <thead>
      <tr>
        <th>Version</th>
        <th>Period</th>
        <th>Org Unit</th>
        <th>Service</th>
        <th>Key Figure</th>
        <th>Value</th>
        <th>Ref. Value</th>
      </tr>
    </thead>
    <tbody>
      {% for f in facts %}
      <tr>
        <td>{{ f.version.code }}</td>
        <td>{{ f.period.name }}</td>
        <td>{{ f.org_unit.name }}</td>
        <td>{% if f.service %}{{ f.service.name }}{% else %}&mdash;{% endif %}</td>
        <td>{{ f.key_figure.code }}</td>
        <td>{{ f.value }}</td>
        <td>{{ f.ref_value }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="7" class="text-center">No facts found for this session.</td></tr>
      {% endfor %}
    </tbody>
  </table>
  {# — The Tabulator grid — #}
  <h2>Current Facts ({{ dr.description }})</h2>
  {% include "bps/_tabulator.html" with api_url=api_url detail_url=detail_url change_url=change_url create_url=create_url export_url=export_url owner_update_url=owner_update_url orgunit_update_url=orgunit_update_url user_ac_url=user_ac_url orgunit_ac_url=orgunit_ac_url %}
  {# — Session actions — #}
  {% if sess.status == sess.Status.DRAFT and request.user == sess.org_unit.head_user %}
    <form method="post" class="mt-3">{% csrf_token %}
      <button name="complete" class="btn btn-success">Mark Completed</button>
    </form>
  {% endif %}
  {% if sess.status == sess.Status.COMPLETED and request.user.is_staff %}
    <form method="post" class="mt-2">{% csrf_token %}
      <button name="freeze" class="btn btn-danger">Freeze Session</button>
    </form>
  {% endif %}
  {% if can_advance %}
    <form
      action="{% url 'bps:advance_stage' session_id=sess.pk %}"
      method="post"
      class="d-inline mt-2"
    >{% csrf_token %}
      <button class="btn btn-sm btn-primary">Next Step ➡️</button>
    </form>
  {% endif %}
{% endblock %}
{% block extra_js %}
  <script>
    // your Vue component for the period table
    const app = Vue.createApp({});
    app.component('vue-period-table', {
      props: ['buckets'],
      template: `
        <table class="table table-bordered mb-4">
          <thead>
            <tr><th v-for="b in buckets">{{ b.name }}</th></tr>
          </thead>
        </table>`
    });
    app.mount('#period-table');
  </script>
{% endblock %}
```

### `bps/session_list.html`
```html
{% extends "bps/base.html" %}
{% load static %}
{% block content %}
<div class="container my-4">
  <h1>All Planning Sessions</h1>
  <table class="table table-hover">
    <thead>
      <tr>
        <th>Org Unit</th>
        <th>Layout / Year • Version</th>
        <th>Status</th>
        <th>Created At</th>
      </tr>
    </thead>
    <tbody>
      {% for sess in sessions %}
      <tr>
        <td>
          <a href="{% url 'bps:session_detail' sess.pk %}">
            {{ sess.org_unit.name }}
          </a>
        </td>
        <td>{{ sess.layout_year.layout.name }} / {{ sess.layout_year.year.code }} • {{ sess.layout_year.version.code }}</td>
        <td>{{ sess.get_status_display }}</td>
        <td>{{ sess.created_at|date:"Y-m-d H:i" }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="4">No sessions found.</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

### `bps/subformula_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<h1>Sub-Formulas</h1>
<form method="post" class="mb-4">{% csrf_token %}
  {{ form|crispy }}
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Expression</th></tr></thead>
  <tbody>
    {% for s in subs %}
      <tr><td>{{ s.name }}</td><td><code>{{ s.expression }}</code></td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

### `bps/variable_list.html`
```html
{% extends "bps/base.html" %}
{% load crispy_forms_tags %}
{% block content %}
<div class="container my-4">
  <h1>Global Variables</h1>
  <form method="post" class="row g-3 align-items-end mb-4">{% csrf_token %}
    <div class="col-md-4">
      {{ form.name|as_crispy_field }}
    </div>
    <div class="col-md-4">
      {{ form.value|as_crispy_field }}
    </div>
    <div class="col-md-8">
      {{ form.description|as_crispy_field }}
    </div>
    <div class="col-md-2">
      <button type="submit" class="btn btn-primary">Add Variable</button>
    </div>
  </form>
  <table class="table table-hover">
    <thead>
      <tr><th>Name</th><th>Value</th><th>Description</th></tr>
    </thead>
    <tbody>
      {% for v in consts %}
      <tr>
        <td>{{ v.name }}</td>
        <td>{{ v.value }}</td>
        <td>{{ v.description }}</td>
      </tr>
      {% empty %}
      <tr><td colspan="3">No variables defined.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endblock %}
```

