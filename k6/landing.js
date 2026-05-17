import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const LANDING_PATH = __ENV.LANDING_PATH || '/';

export const options = {
  discardResponseBodies: false,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    checks: ['rate>0.99'],
  },
  scenarios: {
    landing_baseline: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 20),
      timeUnit: '1s',
      duration: __ENV.DURATION || '5m',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 20),
      maxVUs: Number(__ENV.MAX_VUS || 200),
    },
  },
};

export default function () {
  const res = http.get(`${BASE_URL}${LANDING_PATH}`, {
    tags: { name: 'landing_home' },
  });

  check(res, {
    'landing status is 200': (r) => r.status === 200,
    'landing html received': (r) => r.body && r.body.length > 0,
  });

  sleep(Number(__ENV.SLEEP || 0.2));
}
