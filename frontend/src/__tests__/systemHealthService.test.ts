import { ApiError } from '../services/apiClient';
import { getDegradedSystemHealth } from '../services/systemHealthService';

function assertEquals(actual: unknown, expected: unknown): void {
  if (actual !== expected) throw new Error(`Expected ${String(expected)}, received ${String(actual)}`);
}

const payload = {
  status: 'unhealthy',
  version: '0.1.0',
  database: 'online',
  pg_database: 'online',
  redis: 'online',
  ollama_llm: 'online',
  rule_configuration: 'unavailable',
};

assertEquals(getDegradedSystemHealth(new ApiError('Service unavailable', 503, payload)), payload);
assertEquals(getDegradedSystemHealth(new ApiError('Network request failed', 0)), null);
assertEquals(getDegradedSystemHealth(new ApiError('Invalid degraded payload', 503, {})), null);
