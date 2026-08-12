import {
  buildInitialRuleConfigValue,
  getRuleConfigFieldLabel,
  resolveRuleConfigSchema,
} from '../utils/ruleConfigSchema';
import { RuleConfigJsonSchema } from '../types/api';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

const schema: RuleConfigJsonSchema = {
  type: 'object',
  properties: {
    enabled: { type: 'boolean', default: true },
    limit: { anyOf: [{ type: 'integer' }, { type: 'null' }], default: null },
    thresholds: { $ref: '#/$defs/Thresholds' },
  },
  $defs: {
    Thresholds: {
      type: 'object',
      properties: {
        high: { type: 'number', default: 0.8 },
        labels: { type: 'array', items: { type: 'string' } },
      },
    },
  },
};

assertEquals(resolveRuleConfigSchema(schema.properties!.thresholds, schema).type, 'object');
assertEquals(getRuleConfigFieldLabel('match_high_threshold', {}), 'Match High Threshold');
assertEquals(buildInitialRuleConfigValue(schema, schema), {
  enabled: true,
  limit: null,
  thresholds: { high: 0.8, labels: [] },
});
