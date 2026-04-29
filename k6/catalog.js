import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const CATALOG_PATH = __ENV.CATALOG_PATH || '/';
const LIST_PATH = __ENV.LIST_PATH || '/catalog';
const ITEM_PATH = __ENV.ITEM_PATH || '/catalog/item-1';

export const options = {
  discardResponseBodies: false,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<2000', 'p(99)<5000'],
    checks: ['rate>0.99'],
  },
  scenarios: {
    catalog_stress: {
      executor: 'ramping-arrival-rate',
      startRate: Number(__ENV.START_RATE || 10),
      timeUnit: '1s',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || 50),
      maxVUs: Number(__ENV.MAX_VUS || 500),
      stages: [
        { target: Number(__ENV.STAGE1_TARGET || 20), duration: __ENV.STAGE1_DURATION || '1m' },
        { target: Number(__ENV.STAGE2_TARGET || 50), duration: __ENV.STAGE2_DURATION || '2m' },
        { target: Number(__ENV.STAGE3_TARGET || 100), duration: __ENV.STAGE3_DURATION || '2m' },
        { target: Number(__ENV.STAGE4_TARGET || 150), duration: __ENV.STAGE4_DURATION || '2m' },
        { target: Number(__ENV.STAGE5_TARGET || 0), duration: __ENV.STAGE5_DURATION || '30s' },
      ],
    },
  },
};

export default function () {
  const responses = http.batch([
    ['GET', `${BASE_URL}${CATALOG_PATH}`, null, { tags: { name: 'catalog_home' } }],
    ['GET', `${BASE_URL}${LIST_PATH}`, null, { tags: { name: 'catalog_list' } }],
    ['GET', `${BASE_URL}${ITEM_PATH}`, null, { tags: { name: 'catalog_item' } }],
  ]);

  check(responses[0], {
    'catalog home status is 200': (r) => r.status === 200,
  });

  check(responses[1], {
    'catalog list status is 200': (r) => r.status === 200,
  });

  check(responses[2], {
    'catalog item status is 200': (r) => r.status === 200,
  });

  sleep(Number(__ENV.SLEEP || 0.3));
}
