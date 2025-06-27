// === access001 ===
function compute_access001(params) {
  const series = [];
  series.push({ name: 'A', type: 'bar', data: [ (params.E / 100) * (params.H / 24) ] });
  series.push({ name: 'R', type: 'bar', data: [ Math.min(1, params.H / 12) ] });
  return { series };
}

// === pie003 ===
function compute_pie003(params) {
  const series = [];
  series.push({
    name: 'Energy Mix', type: 'pie', data: [
      { name: 'R', value: params.R },
    { name: 'F', value: params.F },
    { name: 'N', value: params.N }
    ]
  });
  return { series };
}

// === stack004 ===
function compute_stack004(params) {
  const series = [];
  series.push({ name: 'S', type: 'bar', stack: 'stack', data: [ params.S ] });
  series.push({ name: 'W', type: 'bar', stack: 'stack', data: [ params.W ] });
  return { series };
}

// === multi005 ===
function compute_multi005(params) {
  const series = [];
  const xs = Array.from({ length: 21 }, (_, i) => i * 5);
  const y_Y1 = xs.map(x => [x, (params.A / 100) * Math.sin(Math.PI * x / 100) * 10]);
  series.push({ name: 'Y1', type: 'line', data: y_Y1 });
  const y_Y2 = xs.map(x => [x, (params.B / 100) * Math.log(x + 1)]);
  series.push({ name: 'Y2', type: 'line', data: y_Y2 });
  const xAxis = xs;
  return { series, xAxis };
}

// === lcoe001 ===
function compute_lcoe001(params) {
  const series = [];
  const xs = [0, 40, 80, 120, 160, 200, 240, 280, 320, 360, 400, 440, 480, 520, 560, 600, 640, 680, 720, 760, 800, 840, 880, 920, 960, 1000, 1040, 1080, 1120, 1160, 1200, 1240, 1280, 1320, 1360, 1400, 1440, 1480, 1520, 1560, 1600, 1640, 1680, 1720, 1760, 1800, 1840, 1880, 1920, 1960, 2000];
  const y_LCOE_5 = xs.map(x => [x, ((x * 0.05 + params.F) / (params.E - params.V))]);
  series.push({ name: 'LCOE_5', type: 'line', data: y_LCOE_5 });
  const y_LCOE_7 = xs.map(x => [x, ((x * 0.06 + params.F) / (params.E - params.V))]);
  series.push({ name: 'LCOE_7', type: 'line', data: y_LCOE_7 });
  const y_LCOE_10 = xs.map(x => [x, ((x * 0.1 + params.F) / (params.E - params.V))]);
  series.push({ name: 'LCOE_10', type: 'line', data: y_LCOE_10 });
  const xAxis = xs;
  return { series, xAxis };
}

// === range006 ===
function compute_range006(params) {
  const series = [];
  series.push({ name: 'E_min', type: 'bar', data: [ params.N_min * params.F ] });
  series.push({ name: 'E_max', type: 'bar', data: [ params.N_max * params.F ] });
  return { series };
}