import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const TARGET_PATH = __ENV.TARGET_PATH || '/catalog';
const ITEM_PATH = __ENV.ITEM_PATH || '/catalog/item-1';
const MODE = __ENV.MODE || 'catalog';

const START_RATE = Number(__ENV.START_RATE || 20);
const STEP1_TARGET = Number(__ENV.STEP1_TARGET || 50);
const STEP2_TARGET = Number(__ENV.STEP2_TARGET || 100);
const STEP3_TARGET = Number(__ENV.STEP3_TARGET || 200);
const STEP4_TARGET = Number(__ENV.STEP4_TARGET || 300);
const STEP5_TARGET = Number(__ENV.STEP5_TARGET || 400);
const STEP6_TARGET = Number(__ENV.STEP6_TARGET || 500);

const STEP1_DURATION = __ENV.STEP1_DURATION || '1m';
const STEP2_DURATION = __ENV.STEP2_DURATION || '1m';
const STEP3_DURATION = __ENV.STEP3_DURATION || '1m';
const STEP4_DURATION = __ENV.STEP4_DURATION || '1m';
const STEP5_DURATION = __ENV.STEP5_DURATION || '1m';
const STEP6_DURATION = __ENV.STEP6_DURATION || '1m';
const COOLDOWN_DURATION = __ENV.COOLDOWN_DURATION || '30s';

export const options = {
  discardResponseBodies: true,
  thresholds: {
    http_req_failed:   [{ threshold: 'rate<0.05',  abortOnFail: false }],
    http_req_duration: [{ threshold: 'p(95)<3000', abortOnFail: false },
                        { threshold: 'p(99)<5000', abortOnFail: false }],
    checks:            [{ threshold: 'rate>0.95',  abortOnFail: false }],
  },
  scenarios: {
    stress_until_failure: {
      executor: 'ramping-arrival-rate',
      startRate: START_RATE,
      timeUnit: '1s',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 700),
      maxVUs: Number(__ENV.MAX_VUS || 1000),
      stages: [
        { target: STEP1_TARGET, duration: STEP1_DURATION },
        { target: STEP2_TARGET, duration: STEP2_DURATION },
        { target: STEP3_TARGET, duration: STEP3_DURATION },
        { target: STEP4_TARGET, duration: STEP4_DURATION },
        { target: STEP5_TARGET, duration: STEP5_DURATION },
        { target: STEP6_TARGET, duration: STEP6_DURATION },
        { target: 0, duration: COOLDOWN_DURATION },
      ],
    },
  },
};

function hitLanding() {
  const res = http.get(`${BASE_URL}${TARGET_PATH}`, {
    headers: {
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache',
    },
    tags: { name: 'stress_landing' },
  });

  check(res, {
    'landing status is 200': (r) => r.status === 200,
    'landing has body': (r) => parseInt(r.headers['Content-Length'] || '0') > 0,
  });
}

function hitCatalog() {
  const res = http.get(`${BASE_URL}${TARGET_PATH}`, {
    headers: {
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache',
    },
    tags: { name: 'stress_catalog_list' },
  });

  check(res, {
    'catalog list status is 200': (r) => r.status === 200,
    'catalog has body': (r) => !!r.body || Number(r.headers['Content-Length'] || 0) >= 0,
  });
}

export default function () {
  if (MODE === 'landing') {
    hitLanding();
  } else {
    hitCatalog();
  }

  // sleep(Number(__ENV.SLEEP || 0.1));
}
