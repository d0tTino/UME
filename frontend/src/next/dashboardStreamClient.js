import { createDashboardStreamClient } from '../realtimeStream';

export function createNextDashboardStreamClient(config = {}) {
  return createDashboardStreamClient(config);
}

export function connectDashboardStream(config) {
  return createNextDashboardStreamClient(config.client).subscribe(config.subscription);
}
