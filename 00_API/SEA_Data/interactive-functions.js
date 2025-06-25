// === access001 ===
function compute_access001(params) {
  const series = [];
  series.push({ name: 'Access Index', type: 'bar', data: [ (params.E / 100) * (params.H / 24) ] });
  series.push({ name: 'Reliability Index', type: 'bar', data: [ Math.min(1, params.H / 12) ] });
  return { series};
}

// === cost002 ===
function compute_cost002(params) {
  const series = [];
  const xs = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
  const y_Total_Cost = xs.map(x => [x, params.F * (100 / params.T)]);
  series.push({ name: 'Total Cost', type: 'line', data: y_Total_Cost});
  const xAxis = xs;
  return { series, xAxis };
}

// === pie003 ===
function compute_pie003(params) {
  const series = [];
  series.push({
    name: 'Energy Mix', type: 'pie', data: [
      { name: 'Renewables', value: params.R },
    { name: 'Fossils', value: params.F },
    { name: 'Nuclear', value: params.N }
    ]
  });
  return { series};
}

// === stack004 ===
function compute_stack004(params) {
  const series = [];
  series.push({ name: 'Solar', type: 'bar', stack: 'stack', data: [ params.S ] });
  series.push({ name: 'Wind', type: 'bar', stack: 'stack', data: [ params.W ] });
  return { series};
}

// === multi005 ===
function compute_multi005(params) {
  const series = [];
  const xs = Array.from({ length: 21 }, (_, i) => i * 5);
  const y_Sine_Impact = xs.map(x => [x, (params.A / 100) * Math.sin(Math.PI * x / 100) * 10]);
  series.push({ name: 'Sine Impact', type: 'line', data: y_Sine_Impact });
  const y_Logarithmic_Growth = xs.map(x => [x, (params.B / 100) * Math.log(x + 1)]);
  series.push({ name: 'Logarithmic Growth', type: 'line', data: y_Logarithmic_Growth });
  const xAxis = xs;
  return { series, xAxis };
}