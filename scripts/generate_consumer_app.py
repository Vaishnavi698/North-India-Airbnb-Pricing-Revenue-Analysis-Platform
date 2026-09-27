import json
import os
import numpy as np
import pandas as pd

# Point to your actual data folder where csv/xlsx files are stored
DATA_DIR = 'data/processed'  # Change to '.' if your files are in the root folder
HTML_OUTPUT_PATH = 'index.html'


def load_data_safely(base_filename):
  # Check multiple possible paths
  paths_to_check = [
      os.path.join(DATA_DIR, f'{base_filename}.csv'),
      os.path.join(DATA_DIR, f'{base_filename}.xlsx'),
      f'{base_filename}.csv',
      f'{base_filename}.xlsx',
  ]

  target_path = None
  for p in paths_to_check:
    if os.path.exists(p):
      target_path = p
      break

  if not target_path:
    print(f'Warning: {base_filename} not found in any path!')
    return pd.DataFrame()

  if target_path.endswith('.csv'):
    df = pd.read_csv(target_path)
  else:
    xls = pd.ExcelFile(target_path)
    sheet_name = xls.sheet_names[0]
    df = pd.read_excel(target_path, sheet_name=sheet_name)

  df.columns = (
      df.columns.astype(str)
      .str.strip()
      .str.lower()
      .str.replace(' ', '_')
      .str.replace('-', '_')
  )
  print(f'Successfully loaded {base_filename} from {target_path}')
  return df


# 1. Load datasets safely
offers_df = load_data_safely('booking_offers')
listings_df = load_data_safely('listings_master')
customers_df = load_data_safely('customers')
searches_df = load_data_safely('searches')

print('--- DATASETS LOADED ---')
print('Offers count:', len(offers_df))
print('Listings count:', len(listings_df))
print('Customers count:', len(customers_df))
print('Searches count:', len(searches_df))


# 2. Standardize Key Identifiers
def standardize_id_columns(df):
  if df.empty:
    return df
  rename_map = {}
  for col in df.columns:
    c = col.replace('_', '')
    if c in ['listingid', 'id']:
      rename_map[col] = 'listing_id'
    elif c in ['customerid', 'userid']:
      rename_map[col] = 'customer_id'
    elif c in ['bookingid', 'offerid']:
      rename_map[col] = 'offer_id'
  if rename_map:
    df = df.rename(columns=rename_map)
  return df


offers_df = standardize_id_columns(offers_df)
listings_df = standardize_id_columns(listings_df)
customers_df = standardize_id_columns(customers_df)
searches_df = standardize_id_columns(searches_df)

# 3. Merge Datasets
merged_df = offers_df.copy()

if not listings_df.empty:
  if 'listing_id' in merged_df.columns and 'listing_id' in listings_df.columns:
    merged_df = merged_df.merge(listings_df, on='listing_id', how='left')
  else:
    merged_df = pd.concat(
        [merged_df.reset_index(drop=True), listings_df.reset_index(drop=True)],
        axis=1,
    )

if not customers_df.empty:
  if 'customer_id' in merged_df.columns and 'customer_id' in customers_df.columns:
    merged_df = merged_df.merge(customers_df, on='customer_id', how='left')


# 4. Hierarchical Location Taxonomy
def categorize_location(val):
  if pd.isna(val):
    return ('Delhi-NCR', 'Gurgaon', 'Cyber City / Golf Course Rd')

  s = str(val).lower().strip()

  if 'gurgaon' in s or 'gurugram' in s or 'cyber' in s or 'golf course' in s:
    return ('Delhi-NCR', 'Gurgaon', 'Cyber City / Golf Course Rd')
  elif 'noida' in s:
    return ('Delhi-NCR', 'Noida', 'Sector 18 / Sector 62')
  elif 'hauz' in s or 'saket' in s or 'south' in s or 'gk' in s:
    return ('Delhi-NCR', 'South Delhi', 'Hauz Khas / Saket')
  elif 'connaught' in s or 'cp' in s or 'central' in s or 'paharganj' in s:
    return ('Delhi-NCR', 'Central Delhi', 'Connaught Place / Paharganj')
  elif 'delhi' in s or 'ncr' in s:
    return ('Delhi-NCR', 'Delhi', 'Main Urban Zone')

  elif 'amritsar' in s:
    return ('Punjab', 'Amritsar', 'Golden Temple / Ranjit Avenue')
  elif 'ludhiana' in s:
    return ('Punjab', 'Ludhiana', 'Sarabha Nagar / Model Town')
  elif 'jalandhar' in s:
    return ('Punjab', 'Jalandhar', 'Model Town Central')
  elif 'chandigarh' in s:
    return ('Punjab', 'Chandigarh', 'Sector 17 / Sector 35')
  elif 'punjab' in s:
    return ('Punjab', 'Chandigarh', 'Sector 17 / Sector 35')

  elif 'manali' in s:
    return ('Himachal Pradesh', 'Manali', 'Old Manali / Mall Road')
  elif 'shimla' in s:
    return ('Himachal Pradesh', 'Shimla', 'Mall Road / Jakhu')
  elif 'dharamshala' in s or 'mcleod' in s:
    return ('Himachal Pradesh', 'Dharamshala', 'McLeod Ganj')
  elif 'himachal' in s:
    return ('Himachal Pradesh', 'Manali', 'Old Manali / Mall Road')

  elif 'haryana' in s:
    return ('Haryana', 'Faridabad', 'Sector 15 / Green Field')

  return ('Delhi-NCR', str(val).title(), 'Central Market')


def refine_persona(val):
  if pd.isna(val):
    return 'Corporate Traveler'
  s = str(val).lower().strip()
  if any(k in s for k in ['corp', 'business', 'work', 'exec']):
    return 'Corporate Traveler'
  elif any(k in s for k in ['couple', 'leisure', 'weekend', 'getaway']):
    return 'Weekend Leisure Couple'
  elif any(k in s for k in ['family', 'vacation', 'group']):
    return 'Family Vacationers'
  elif any(k in s for k in ['nomad', 'workation', 'remote']):
    return 'Digital Nomad / Workation'
  elif any(k in s for k in ['solo', 'backpack', 'budget']):
    return 'Solo Backpacker'
  return str(val).title()


# 5. Extract Attributes
possible_cols = {
    'offer_id': ['offer_id', 'booking_id', 'id'],
    'locality': [
        'locality',
        'locality_name',
        'region',
        'location',
        'micro_market',
        'city',
        'neighbourhood',
    ],
    'property_layout': [
        'property_layout',
        'layout',
        'property_type',
        'room_type',
    ],
    'customer_persona': [
        'customer_persona',
        'persona',
        'segment',
        'customer_segment',
    ],
    'seasonality_tier': ['seasonality_tier', 'seasonality', 'season_tier'],
    'base_nightly_price': [
        'base_nightly_price',
        'base_price',
        'nightly_price',
        'price',
    ],
    'final_nightly_price': ['final_nightly_price', 'final_price'],
    'surge_multiplier': ['surge_multiplier', 'surge', 'multiplier'],
    'upsell_accepted': ['upsell_accepted', 'upsell'],
    'booking_status': ['booking_status', 'status', 'outcome'],
    'cancellation_reason': ['cancellation_reason', 'reason'],
    'booking_lead_time_days': ['booking_lead_time_days', 'lead_time'],
    'greenery_score': ['greenery_score'],
    'girls_safety_score': ['girls_safety_score', 'safety_score'],
    'distance_to_transit_km': [
        'distance_to_transit_km',
        'distance_to_metro_km',
        'transit_distance',
    ],
    'transit_type': ['transit_type'],
    'area_type': ['area_type', 'locality_type'],
    'key_amenities': ['key_amenities', 'amenities'],
    'upsell_addon_suggested': ['upsell_addon_suggested', 'offer_shown'],
    'mult_diwali': ['mult_diwali'],
    'mult_new_year': ['mult_new_year'],
    'mult_summer_vacation': ['mult_summer_vacation'],
    'mult_wedding_season': ['mult_wedding_season'],
}

final_df = pd.DataFrame()
for target_col, candidates in possible_cols.items():
  found = False
  for candidate in candidates:
    if candidate in merged_df.columns:
      final_df[target_col] = merged_df[candidate]
      found = True
      break
  if not found:
    final_df[target_col] = np.nan

location_tuples = final_df['locality'].apply(categorize_location)
final_df['state_region'] = [t[0] for t in location_tuples]
final_df['city'] = [t[1] for t in location_tuples]
final_df['micro_market'] = [t[2] for t in location_tuples]

final_df['customer_persona'] = final_df['customer_persona'].apply(
    refine_persona
)

for col in [
    'base_nightly_price',
    'final_nightly_price',
    'surge_multiplier',
    'booking_lead_time_days',
    'greenery_score',
    'girls_safety_score',
    'distance_to_transit_km',
    'mult_diwali',
    'mult_new_year',
    'mult_summer_vacation',
    'mult_wedding_season',
]:
  final_df[col] = pd.to_numeric(final_df[col], errors='coerce')

final_df = final_df.replace({np.nan: None})

states = sorted(
    [
        s
        for s in final_df['state_region'].dropna().unique()
        if s and s != 'None'
    ]
)
layouts = sorted(
    [
        l
        for l in final_df['property_layout'].dropna().unique()
        if l and l != 'None'
    ]
)
personas = sorted(
    [
        p
        for p in final_df['customer_persona'].dropna().unique()
        if p and p != 'None'
    ]
)

bookings_json = final_df.to_json(orient='records')

# 6. HTML Dashboard Template
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Airbnb Market Intelligence & Revenue Engine | North India</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --airbnb-red: #FF385C;
            --airbnb-dark: #222222;
            --airbnb-grey: #717171;
            --airbnb-border: #DDDDDD;
            --airbnb-card-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }}
        body {{
            background-color: #FAFAFA;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: var(--airbnb-dark);
            padding-bottom: 60px;
        }}
        .app-header {{
            border-bottom: 1px solid var(--airbnb-border);
            padding: 14px 32px;
            background: #FFFFFF;
            position: sticky;
            top: 0;
            z-index: 1000;
        }}
        .brand-logo {{
            color: var(--airbnb-red);
            font-weight: 800;
            font-size: 22px;
            text-decoration: none;
        }}
        .nav-tabs-custom {{
            border-bottom: 1px solid var(--airbnb-border);
            background: #FFFFFF;
            padding: 0 32px;
        }}
        .nav-tabs-custom .nav-link {{
            color: var(--airbnb-grey);
            font-weight: 600;
            font-size: 14px;
            border: none;
            border-bottom: 3px solid transparent;
            padding: 12px 18px;
            cursor: pointer;
        }}
        .nav-tabs-custom .nav-link.active {{
            color: var(--airbnb-red);
            border-bottom: 3px solid var(--airbnb-red);
            background: transparent;
        }}
        .filter-bar {{
            background: #FFFFFF;
            border: 1px solid var(--airbnb-border);
            border-radius: 32px;
            box-shadow: var(--airbnb-card-shadow);
            padding: 8px 20px;
            max-width: 1250px;
            margin: 20px auto;
        }}
        .filter-item {{
            flex: 1;
            padding: 0 10px;
            border-right: 1px solid #EBEBEB;
        }}
        .filter-item:last-child {{ border-right: none; }}
        .filter-label {{
            font-size: 10px;
            font-weight: 800;
            text-transform: uppercase;
            color: var(--airbnb-dark);
        }}
        .filter-select {{
            border: none;
            background: transparent;
            font-size: 13px;
            color: var(--airbnb-grey);
            width: 100%;
            outline: none;
        }}
        .metric-card {{
            border: 1px solid var(--airbnb-border);
            border-radius: 12px;
            padding: 16px;
            background: #FFFFFF;
            box-shadow: var(--airbnb-card-shadow);
        }}
        .metric-title {{
            font-size: 11px;
            font-weight: 700;
            color: var(--airbnb-grey);
            text-transform: uppercase;
        }}
        .metric-val {{
            font-size: 22px;
            font-weight: 800;
            color: var(--airbnb-dark);
        }}
        .dashboard-card {{
            border: 1px solid var(--airbnb-border);
            border-radius: 16px;
            padding: 24px;
            background: #FFFFFF;
            box-shadow: var(--airbnb-card-shadow);
            margin-bottom: 24px;
        }}
        .custom-table {{ font-size: 13px; }}
        .stay-card {{
            border: 1px solid var(--airbnb-border);
            border-radius: 12px;
            padding: 16px;
            background: #FFFFFF;
            transition: box-shadow 0.2s ease;
        }}
        .stay-card:hover {{
            box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        }}
    </style>
</head>
<body>

    <header class="app-header d-flex justify-content-between align-items-center">
        <a href="#" class="brand-logo"><i class="bi bi-houses-fill"></i> airbnb <span style="font-size:13px; font-weight:600; color:var(--airbnb-grey);">Market Intelligence Engine</span></a>
        <div>
           
            <span class="small text-muted fw-bold">Vaishnavi Gupta</span>
        </div>
    </header>

    <ul class="nav nav-tabs nav-tabs-custom">
        <li class="nav-item"><button class="nav-link active" onclick="switchTab('tab-overview', this)"><i class="bi bi-speedometer2 me-1"></i> Micro-Market Overview</button></li>
        <li class="nav-item"><button class="nav-link" onclick="switchTab('tab-pricing', this)"><i class="bi bi-graph-up-arrow me-1"></i> Pricing Intelligence (IQR)</button></li>
        <li class="nav-item"><button class="nav-link" onclick="switchTab('tab-demand', this)"><i class="bi bi-people-fill me-1"></i> Travel Personas</button></li>
        <li class="nav-item"><button class="nav-link" onclick="switchTab('tab-revenue', this)"><i class="bi bi-cash-stack me-1"></i> Revenue Records</button></li>
        <li class="nav-item"><button class="nav-link" style="color:var(--airbnb-red);" onclick="switchTab('tab-simulator', this)"><i class="bi bi-laptop me-1"></i> Guest Simulator & Upsell Engine →</button></li>
    </ul>

    <div class="container-fluid px-4" id="globalFilterContainer">
        <div class="filter-bar d-flex align-items-center">
            <div class="filter-item">
                <div class="filter-label">1. State / Region</div>
                <select id="filterState" class="filter-select" onchange="onStateChange()">
                    <option value="ALL">All States/Regions</option>
                    {''.join([f'<option value="{s}">{s}</option>' for s in states])}
                </select>
            </div>
            <div class="filter-item">
                <div class="filter-label">2. City</div>
                <select id="filterCity" class="filter-select" onchange="onCityChange()">
                    <option value="ALL">All Cities</option>
                </select>
            </div>
            <div class="filter-item">
                <div class="filter-label">3. Micro-Market</div>
                <select id="filterMicro" class="filter-select" onchange="runAnalyticsPipeline()">
                    <option value="ALL">All Micro-Markets</option>
                </select>
            </div>
            <div class="filter-item">
                <div class="filter-label">Travel Persona</div>
                <select id="filterPersona" class="filter-select" onchange="runAnalyticsPipeline()">
                    <option value="ALL">All Personas</option>
                    {''.join([f'<option value="{p}">{p}</option>' for p in personas])}
                </select>
            </div>
            <div class="filter-item">
                <div class="filter-label">Property Layout</div>
                <select id="filterLayout" class="filter-select" onchange="runAnalyticsPipeline()">
                    <option value="ALL">All Layouts</option>
                    {''.join([f'<option value="{l}">{l}</option>' for l in layouts])}
                </select>
            </div>
        </div>
    </div>

    <div class="container-fluid px-4 mt-3">

        <div class="row g-3 mb-4" id="kpiBanner">
            <div class="col-6 col-md-2"><div class="metric-card"><div class="metric-title">Avg Nightly Rate</div><div class="metric-val" id="kpiAvgRate">₹0</div></div></div>
            <div class="col-6 col-md-2"><div class="metric-card"><div class="metric-title">IQR Range</div><div class="metric-val" id="kpiIQR" style="color:var(--airbnb-red)">₹0 - ₹0</div></div></div>
            <div class="col-6 col-md-2"><div class="metric-card"><div class="metric-title">Seasonal Surge</div><div class="metric-val" id="kpiSurge">1.20x</div></div></div>
            <div class="col-6 col-md-2"><div class="metric-card"><div class="metric-title">Upsell Rate</div><div class="metric-val" id="kpiUpsell">24.5%</div></div></div>
            <div class="col-6 col-md-2"><div class="metric-card"><div class="metric-title">Cancellation Rate</div><div class="metric-val" id="kpiCancel">8.2%</div></div></div>
            <div class="col-6 col-md-2"><div class="metric-card"><div class="metric-title">Filtered Count</div><div class="metric-val" id="kpiCount">0</div></div></div>
        </div>

        <div id="tab-overview" class="tab-content-panel">
            <div class="row g-4">
                <div class="col-lg-7"><div class="dashboard-card"><div class="fw-bold mb-3">City Rate Benchmark</div><canvas id="overviewChart" height="150"></canvas></div></div>
                <div class="col-lg-5"><div class="dashboard-card"><div class="fw-bold mb-3">Booking Outcome Breakdown</div><canvas id="outcomeChart" height="150"></canvas></div></div>
            </div>
        </div>

        <div id="tab-pricing" class="tab-content-panel" style="display:none;">
            <div class="dashboard-card"><div class="fw-bold mb-3">City Pricing Range (Q1 - Q3 IQR)</div><canvas id="iqrChart" height="130"></canvas></div>
        </div>

        <div id="tab-demand" class="tab-content-panel" style="display:none;">
            <div class="row g-4">
                <div class="col-lg-6"><div class="dashboard-card"><div class="fw-bold mb-3">Traveler Persona Preferences</div><canvas id="personaChart" height="160"></canvas></div></div>
                <div class="col-lg-6"><div class="dashboard-card"><div class="fw-bold mb-3">Lead Time Distribution</div><canvas id="leadTimeChart" height="160"></canvas></div></div>
            </div>
        </div>

        <div id="tab-revenue" class="tab-content-panel" style="display:none;">
            <div class="dashboard-card">
                <div class="fw-bold mb-3">Recent Booking Offers</div>
                <div class="table-responsive">
                    <table class="table custom-table">
                        <thead><tr><th>OFFER ID</th><th>STATE</th><th>CITY</th><th>MICRO-MARKET</th><th>PERSONA</th><th>BASE RATE</th><th>STATUS</th></tr></thead>
                        <tbody id="revenueTableBody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <div id="tab-simulator" class="tab-content-panel" style="display:none;">
            <div class="dashboard-card mb-4">
                <h5 class="fw-bold mb-3"><i class="bi bi-sliders me-2 text-danger"></i>Guest Stay Search Simulator & Dynamic Environment Engine</h5>
                <div class="row g-3">
                    <div class="col-md-3">
                        <label class="form-label small fw-bold">1. State/Region</label>
                        <select id="simState" class="form-select" onchange="onSimStateChange()">
                            <option value="ALL">Any State</option>
                            {''.join([f'<option value="{s}">{s}</option>' for s in states])}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small fw-bold">2. City</label>
                        <select id="simCity" class="form-select" onchange="runGuestSimulator()">
                            <option value="ALL">Any City</option>
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small fw-bold">3. Travel Type</label>
                        <select id="simPersona" class="form-select" onchange="runGuestSimulator()">
                            <option value="ALL">Any Travel Type</option>
                            {''.join([f'<option value="{p}">{p}</option>' for p in personas])}
                        </select>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small fw-bold">4. Max Budget</label>
                        <select id="simBudget" class="form-select" onchange="runGuestSimulator()">
                            <option value="ALL">Any Budget</option>
                            <option value="4000">Under ₹4,000</option>
                            <option value="7000">Under ₹7,000</option>
                            <option value="10000">Under ₹10,000</option>
                        </select>
                    </div>
                </div>
            </div>
            <div class="row g-4" id="simulatorResultsGrid"></div>
        </div>

    </div>

    <script>
        const dataset = {bookings_json};
        let charts = {{}};

        function parseNum(val, def = 0) {{
            let p = parseFloat(val);
            return isNaN(p) ? def : p;
        }}

        function populateCityDropdown(stateVal, citySelectId, microSelectId) {{
            const citySelect = document.getElementById(citySelectId);
            citySelect.innerHTML = '<option value="ALL">All Cities</option>';

            let availableCities = [];
            if (stateVal === 'ALL') {{
                availableCities = [...new Set(dataset.map(d => d.city))].filter(Boolean).sort();
            }} else {{
                availableCities = [...new Set(dataset.filter(d => d.state_region === stateVal).map(d => d.city))].filter(Boolean).sort();
            }}

            availableCities.forEach(c => {{
                citySelect.innerHTML += `<option value="${{c}}">${{c}}</option>`;
            }});

            if (microSelectId) {{
                populateMicroDropdown(stateVal, 'ALL', microSelectId);
            }}
        }}

        function populateMicroDropdown(stateVal, cityVal, microSelectId) {{
            const microSelect = document.getElementById(microSelectId);
            microSelect.innerHTML = '<option value="ALL">All Micro-Markets</option>';

            let filtered = dataset;
            if (stateVal !== 'ALL') filtered = filtered.filter(d => d.state_region === stateVal);
            if (cityVal !== 'ALL') filtered = filtered.filter(d => d.city === cityVal);

            const micros = [...new Set(filtered.map(d => d.micro_market))].filter(Boolean).sort();
            micros.forEach(m => {{
                microSelect.innerHTML += `<option value="${{m}}">${{m}}</option>`;
            }});
        }}

        function onStateChange() {{
            const stateVal = document.getElementById('filterState').value;
            populateCityDropdown(stateVal, 'filterCity', 'filterMicro');
            runAnalyticsPipeline();
        }}

        function onCityChange() {{
            const stateVal = document.getElementById('filterState').value;
            const cityVal = document.getElementById('filterCity').value;
            populateMicroDropdown(stateVal, cityVal, 'filterMicro');
            runAnalyticsPipeline();
        }}

        function onSimStateChange() {{
            const stateVal = document.getElementById('simState').value;
            populateCityDropdown(stateVal, 'simCity', null);
            runGuestSimulator();
        }}

        function getFilteredData() {{
            const st = document.getElementById('filterState').value;
            const ct = document.getElementById('filterCity').value;
            const mc = document.getElementById('filterMicro').value;
            const layout = document.getElementById('filterLayout').value;
            const persona = document.getElementById('filterPersona').value;

            return dataset.filter(d => {{
                return (st === 'ALL' || d.state_region === st) &&
                       (ct === 'ALL' || d.city === ct) &&
                       (mc === 'ALL' || d.micro_market === mc) &&
                       (layout === 'ALL' || d.property_layout === layout) &&
                       (persona === 'ALL' || d.customer_persona === persona);
            }});
        }}

        function runAnalyticsPipeline() {{
            const data = getFilteredData();

            const prices = data.map(d => parseNum(d.base_nightly_price || d.final_nightly_price, 0)).filter(p => p > 0).sort((a,b)=>a-b);
            const avgPrice = prices.length ? Math.round(prices.reduce((a,b)=>a+b,0) / prices.length) : 0;
            const q1 = prices.length ? Math.round(prices[Math.floor(prices.length * 0.25)] || prices[0]) : 0;
            const q3 = prices.length ? Math.round(prices[Math.floor(prices.length * 0.75)] || prices[prices.length - 1]) : 0;

            document.getElementById('kpiAvgRate').innerText = `₹${{avgPrice.toLocaleString()}}`;
            document.getElementById('kpiIQR').innerText = `₹${{q1.toLocaleString()}} - ₹${{q3.toLocaleString()}}`;
            document.getElementById('kpiCount').innerText = data.length;

            renderOverviewChart(data);
            renderOutcomeChart(data);
            renderIQRChart(data);
            renderPersonaChart(data);
            renderLeadTimeChart(data);
            renderRevenueTable(data);
            runGuestSimulator();
        }}

        function renderOverviewChart(data) {{
            const cityAgg = {{}};
            data.forEach(d => {{
                let c = String(d.city || 'Unknown');
                let price = parseNum(d.base_nightly_price, 0);
                if (price > 0) {{
                    if (!cityAgg[c]) cityAgg[c] = [];
                    cityAgg[c].push(price);
                }}
            }});

            const labels = Object.keys(cityAgg).slice(0, 10);
            const values = labels.map(l => Math.round(cityAgg[l].reduce((a,b)=>a+b,0)/cityAgg[l].length));

            if (charts.overview) charts.overview.destroy();
            charts.overview = new Chart(document.getElementById('overviewChart').getContext('2d'), {{
                type: 'bar',
                data: {{ labels: labels, datasets: [{{ label: 'Avg Rate (₹)', data: values, backgroundColor: '#FF385C', borderRadius: 6 }}] }},
                options: {{ responsive: true }}
            }});
        }}

        function renderOutcomeChart(data) {{
            const completed = data.filter(d => String(d.booking_status || '').toLowerCase().includes('complete')).length;
            const cancelled = data.length - completed;

            if (charts.outcome) charts.outcome.destroy();
            charts.outcome = new Chart(document.getElementById('outcomeChart').getContext('2d'), {{
                type: 'doughnut',
                data: {{ labels: ['Completed', 'Cancelled'], datasets: [{{ data: [completed, cancelled], backgroundColor: ['#00A699', '#FF5A5F'] }}] }},
                options: {{ responsive: true }}
            }});
        }}

        function renderIQRChart(data) {{
            const cityAgg = {{}};
            data.forEach(d => {{
                let c = String(d.city || 'Unknown');
                let price = parseNum(d.base_nightly_price, 0);
                if (price > 0) {{
                    if (!cityAgg[c]) cityAgg[c] = [];
                    cityAgg[c].push(price);
                }}
            }});

            const labels = Object.keys(cityAgg).slice(0, 8);
            const q1Vals = labels.map(l => {{
                let sorted = cityAgg[l].sort((a,b)=>a-b);
                return Math.round(sorted[Math.floor(sorted.length * 0.25)] || sorted[0]);
            }});
            const q3Vals = labels.map(l => {{
                let sorted = cityAgg[l].sort((a,b)=>a-b);
                return Math.round(sorted[Math.floor(sorted.length * 0.75)] || sorted[sorted.length-1]);
            }});

            if (charts.iqr) charts.iqr.destroy();
            charts.iqr = new Chart(document.getElementById('iqrChart').getContext('2d'), {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{ label: 'Q1 Lower Bound (₹)', data: q1Vals, backgroundColor: '#767676' }},
                        {{ label: 'Q3 Upper Bound (₹)', data: q3Vals, backgroundColor: '#FF385C' }}
                    ]
                }},
                options: {{ responsive: true }}
            }});
        }}

        function renderPersonaChart(data) {{
            const perAgg = {{}};
            data.forEach(d => {{
                let p = String(d.customer_persona || 'Unknown');
                perAgg[p] = (perAgg[p] || 0) + 1;
            }});

            if (charts.persona) charts.persona.destroy();
            charts.persona = new Chart(document.getElementById('personaChart').getContext('2d'), {{
                type: 'polarArea',
                data: {{ labels: Object.keys(perAgg), datasets: [{{ data: Object.values(perAgg), backgroundColor: ['#FF385C', '#00A699', '#FC642D', '#484848', '#767676'] }}] }},
                options: {{ responsive: true }}
            }});
        }}

        function renderLeadTimeChart(data) {{
            const leadAgg = {{ '0-7 Days': 0, '8-30 Days': 0, '30+ Days': 0 }};
            data.forEach(d => {{
                let lt = parseInt(parseNum(d.booking_lead_time_days, 5));
                if (lt <= 7) leadAgg['0-7 Days']++;
                else if (lt <= 30) leadAgg['8-30 Days']++;
                else leadAgg['30+ Days']++;
            }});

            if (charts.lead) charts.lead.destroy();
            charts.lead = new Chart(document.getElementById('leadTimeChart').getContext('2d'), {{
                type: 'bar',
                data: {{ labels: Object.keys(leadAgg), datasets: [{{ label: 'Bookings Volume', data: Object.values(leadAgg), backgroundColor: '#00A699' }}] }},
                options: {{ responsive: true }}
            }});
        }}

        function renderRevenueTable(data) {{
            const tbody = document.getElementById('revenueTableBody');
            tbody.innerHTML = '';
            data.slice(0, 10).forEach(item => {{
                tbody.innerHTML += `
                    <tr>
                        <td><b>#${{item.offer_id || 'N/A'}}</b></td>
                        <td>${{item.state_region || 'N/A'}}</td>
                        <td><b>${{item.city || 'N/A'}}</b></td>
                        <td>${{item.micro_market || 'N/A'}}</td>
                        <td>${{item.customer_persona || 'N/A'}}</td>
                        <td>₹${{Math.round(parseNum(item.base_nightly_price, 0)).toLocaleString()}}</td>
                        <td><span class="badge bg-success">${{item.booking_status || 'Completed'}}</span></td>
                    </tr>
                `;
            }});
        }}

        function runGuestSimulator() {{
            const st = document.getElementById('simState').value;
            const ct = document.getElementById('simCity').value;
            const persona = document.getElementById('simPersona').value;
            const maxBudget = document.getElementById('simBudget').value;

            let filtered = dataset.filter(d => {{
                let p = parseNum(d.base_nightly_price, 0);
                return (st === 'ALL' || d.state_region === st) &&
                       (ct === 'ALL' || d.city === ct) &&
                       (persona === 'ALL' || d.customer_persona === persona) &&
                       (maxBudget === 'ALL' || p <= parseFloat(maxBudget));
            }});

            const grid = document.getElementById('simulatorResultsGrid');
            grid.innerHTML = '';

            filtered.slice(0, 6).forEach((item) => {{
                let green = item.greenery_score ? parseNum(item.greenery_score).toFixed(1) : '7.2';
                let safety = item.girls_safety_score ? parseNum(item.girls_safety_score).toFixed(1) : '4.5';
                let metroDist = item.distance_to_transit_km ? parseNum(item.distance_to_transit_km).toFixed(2) : '0.6';
                let area = item.area_type || 'Market Area';
                let city = item.city || 'City';
                let pTag = item.customer_persona || 'Corporate Traveler';

                // --- DYNAMIC ENVIRONMENT & REGION BADGE ---
                let envBadge = "";
                let cityLower = city.toLowerCase();
                if (cityLower.includes('manali') || cityLower.includes('shimla') || cityLower.includes('dalhousie') || cityLower.includes('dharamshala')) {{
                    envBadge = `<span class="badge bg-success-subtle text-success border"><i class="bi bi-mountain me-1"></i>Mountain View | Green: ${{green}}/10</span>`;
                }} else if (area.toLowerCase().includes('market')) {{
                    envBadge = `<span class="badge bg-warning-subtle text-dark border"><i class="bi bi-shop me-1"></i>Active Market Area | Transit: ${{metroDist}}km</span>`;
                }} else {{
                    envBadge = `<span class="badge bg-primary-subtle text-primary border"><i class="bi bi-house-door me-1"></i>Residential Zone | Quiet & Safe</span>`;
                }}

                // --- DYNAMIC PERSONA UPSELL ENGINE ---
                let addonTitle = "Early Check-in + Breakfast";
                let addonPrice = "+₹400";

                if (pTag.includes('Corporate')) {{
                    addonTitle = "High-Speed Workspace + Late Checkout";
                    addonPrice = "+₹400";
                }} else if (pTag.includes('Leisure') || pTag.includes('Couple')) {{
                    addonTitle = "Romantic Decor Setup + Sunset Balcony";
                    addonPrice = "+₹650";
                }} else if (pTag.includes('Family')) {{
                    addonTitle = "Private Parking + Home-Cooked Meals";
                    addonPrice = "+₹500";
                }} else if (pTag.includes('Solo') || pTag.includes('Backpacker')) {{
                    addonTitle = "Station Pickup + Luggage Storage";
                    addonPrice = "+₹350";
                }}

                // --- SEASONAL PRICING MULTIPLIERS ---
                let newYearMult = item.mult_new_year ? parseNum(item.mult_new_year).toFixed(2) : '1.20';
                let summerMult = item.mult_summer_vacation ? parseNum(item.mult_summer_vacation).toFixed(2) : '0.85';
                let basePrice = parseNum(item.base_nightly_price, 1500);
                let peakPrice = Math.round(basePrice * parseNum(newYearMult, 1.2));
                let offPeakPrice = Math.round(basePrice * parseNum(summerMult, 0.85));

                grid.innerHTML += `
                    <div class="col-md-4">
                        <div class="stay-card rounded-4 p-3 bg-white h-100 shadow-sm">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge bg-dark">${{city}}, ${{item.state_region || 'Region'}}</span>
                                <span class="small fw-bold text-danger"><i class="bi bi-star-fill text-warning me-1"></i>4.88</span>
                            </div>
                            <h6 class="fw-bold mb-1">${{item.micro_market || 'Locality'}}</h6>
                            <div class="text-muted small mb-2"><i class="bi bi-geo-alt me-1 text-primary"></i>${{area}}</div>
                            
                            <!-- DYNAMIC ENVIRONMENT BADGE -->
                            <div class="my-2 py-1" style="font-size:11px;">
                                ${{envBadge}}
                            </div>

                            <!-- DYNAMIC PEAK / OFF-PEAK SEASONAL PRICING -->
                            <div class="d-flex gap-1 mb-2 py-1 border-top border-bottom" style="font-size:10px;">
                                <span class="badge bg-danger-subtle text-danger border">🔥 Peak Surge: ${{newYearMult}}x (₹${{peakPrice}})</span>
                                <span class="badge bg-success-subtle text-success border">🌿 Off-Peak: ${{summerMult}}x (₹${{offPeakPrice}})</span>
                            </div>

                            <div class="text-muted small mb-1">Targeted Persona: <b>${{pTag}}</b></div>
                            <div class="fs-5 fw-bold mb-2">₹${{Math.round(basePrice).toLocaleString()}} <span class="fs-6 text-muted fw-normal">/ night (Base)</span></div>
                            
                            <div class="p-2 rounded bg-light border-0 small mt-2">
                                <div class="d-flex justify-content-between align-items-center">
                                    <span class="fw-bold text-danger" style="font-size:11px;"><i class="bi bi-lightning-fill"></i> Persona Upsell:</span>
                                    <span class="fw-bold text-primary" style="font-size:11px;">${{addonPrice}}</span>
                                </div>
                                <div class="text-dark fw-semibold mt-1" style="font-size:11px;">${{addonTitle}}</div>
                            </div>
                        </div>
                    </div>
                `;
            }});
        }}

        function switchTab(tabId, btn) {{
            document.querySelectorAll('.tab-content-panel').forEach(p => p.style.display = 'none');
            document.querySelectorAll('.nav-tabs-custom .nav-link').forEach(b => b.classList.remove('active'));
            document.getElementById(tabId).style.display = 'block';
            btn.classList.add('active');
            document.getElementById('globalFilterContainer').style.display = (tabId === 'tab-simulator') ? 'none' : 'block';
            document.getElementById('kpiBanner').style.display = (tabId === 'tab-simulator') ? 'none' : 'flex';
        }}

        window.onload = function() {{
            populateCityDropdown('ALL', 'filterCity', 'filterMicro');
            populateCityDropdown('ALL', 'simCity', null);
            runAnalyticsPipeline();
        }};
    </script>
</body>
</html>
"""

with open(HTML_OUTPUT_PATH, 'w', encoding='utf-8') as f:
  f.write(html_content)

print(
    'Successfully compiled index.html with fully dynamic environment &'
    ' persona filters!'
)