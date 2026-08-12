import { RuleConfigJsonSchema } from '@/types/api';

export type RuleConfigValue = unknown;

export const getRuleConfigFieldLabel = (name: string, schema: RuleConfigJsonSchema): string => {
  if (schema.title) return schema.title;
  return name.replace(/_/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
};

export const resolveRuleConfigSchema = (
  schema: RuleConfigJsonSchema,
  root: RuleConfigJsonSchema,
): RuleConfigJsonSchema => {
  if (schema.$ref) {
    const name = schema.$ref.split('/').pop();
    return name && root.$defs?.[name] ? resolveRuleConfigSchema(root.$defs[name], root) : schema;
  }
  if (schema.anyOf) {
    const concrete = schema.anyOf.find((candidate) => candidate.type !== 'null');
    return concrete ? resolveRuleConfigSchema(concrete, root) : schema;
  }
  return schema;
};

export const buildInitialRuleConfigValue = (
  schema: RuleConfigJsonSchema,
  root: RuleConfigJsonSchema,
): RuleConfigValue => {
  if (schema.default !== undefined) return structuredCloneValue(schema.default);
  if (schema.anyOf?.some((candidate) => candidate.type === 'null')) return null;

  const resolved = resolveRuleConfigSchema(schema, root);
  if (resolved.properties) {
    return Object.fromEntries(
      Object.entries(resolved.properties).map(([name, child]) => [name, buildInitialRuleConfigValue(child, root)]),
    );
  }
  if (resolved.type === 'object' || resolved.additionalProperties) return {};
  if (resolved.type === 'array') return [];
  if (resolved.type === 'boolean') return false;
  return '';
};

const structuredCloneValue = (value: unknown): unknown => {
  if (value === null || typeof value !== 'object') return value;
  return JSON.parse(JSON.stringify(value));
};
