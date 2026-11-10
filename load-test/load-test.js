import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// App address inside the cluster (ClusterIP Service), port 5000
const BASE_URL         = __ENV.BASE_URL         || 'http://crud-app.crud.svc.cluster.local:5000';
const NAMES_ENDPOINT   = `${BASE_URL}/api/names`;
const THINK_TIME_SEC   = Number(__ENV.THINK_TIME_SEC) || 0.5;
const REQUEST_TIMEOUT  = __ENV.REQUEST_TIMEOUT  || '30s';

const JSON_HEADERS = {
  headers: { 'Content-Type': 'application/json' },
  timeout: REQUEST_TIMEOUT,
};

export const options = {
  stages: [
    { duration: '10s', target: 100 }, // warm-up
    { duration: '10s', target: 500 }, // ramp to peak
    { duration: '60s', target: 500 }, // sustain peak (60s minimum, as required)
    { duration: '10s', target: 0   }, // cool-down
  ],
  thresholds: {
    http_req_duration:  ['p(95)<500'],  // 95% of requests under 500ms
    'error_rate':       ['rate<0.05'],  // fewer than 5% failed requests
    'checks':           ['rate>0.95'],  // at least 95% of checks pass
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

const createLatency  = new Trend('create_latency', true);
const listLatency    = new Trend('list_latency',   true);
const updateLatency  = new Trend('update_latency', true);
const deleteLatency  = new Trend('delete_latency', true);

const errorRate      = new Rate('error_rate');
const namesCreated   = new Counter('names_created');


function trackErrors(response) {
  errorRate.add(!response || response.status >= 400);
}

function extractId(response) {
  try {
    return JSON.parse(response.body).id ?? null;
  } catch (_) {
    return null;
  }
}

function buildName() {
  return `name-vu${__VU}-iter${__ITER}`;
}


function createName() {
  const payload = JSON.stringify({ name: buildName() });
  const response = http.post(NAMES_ENDPOINT, payload, JSON_HEADERS);

  createLatency.add(response.timings.duration);
  check(response, { 'create → 201': (r) => r.status === 201 });
  trackErrors(response);

  if (response.status === 201) namesCreated.add(1);
  return response;
}

function listNames() {
  const response = http.get(NAMES_ENDPOINT, { timeout: REQUEST_TIMEOUT });

  listLatency.add(response.timings.duration);
  check(response, { 'list → 200': (r) => r.status === 200 });
  trackErrors(response);
  return response;
}

function updateName(id) {
  const payload = JSON.stringify({ name: `${buildName()}-updated` });
  const response = http.put(`${NAMES_ENDPOINT}/${id}`, payload, JSON_HEADERS);

  updateLatency.add(response.timings.duration);
  check(response, { 'update → 200': (r) => r.status === 200 });
  trackErrors(response);
  return response;
}

function deleteName(id) {
  const response = http.del(`${NAMES_ENDPOINT}/${id}`, null, { timeout: REQUEST_TIMEOUT });

  deleteLatency.add(response.timings.duration);
  check(response, { 'delete → 204': (r) => r.status === 204 });
  trackErrors(response);
  return response;
}

export default function () {
  const createResponse = createName();
  listNames();

  const id = extractId(createResponse);
  if (id) {
    updateName(id);
    deleteName(id);
  }

  sleep(THINK_TIME_SEC);
}