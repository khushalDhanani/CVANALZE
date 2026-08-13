import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { AlertCircle, Check, Plus, RotateCcw, Trash2 } from 'lucide-react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Breadcrumbs, Button, Card, PageHeader } from '@/components/ui';
import { COLORS } from '@/constants/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ApiError } from '@/services/apiClient';
import { configService } from '@/services/configService';
import { RuleConfigJsonSchema } from '@/types/api';
import {
  buildInitialRuleConfigValue,
  getRuleConfigFieldLabel,
  resolveRuleConfigSchema,
  RuleConfigValue,
} from '@/utils/ruleConfigSchema';

const getSafeErrorMessage = (reason: unknown, fallback: string): string => {
  if (!(reason instanceof ApiError)) return reason instanceof Error ? reason.message : fallback;
  const violations = reason.data?.error?.details?.violations;
  if (!Array.isArray(violations) || violations.length === 0) return reason.message || fallback;
  return violations
    .slice(0, 8)
    .map((violation: unknown) => {
      const detail = violation && typeof violation === 'object' ? violation as Record<string, unknown> : {};
      return `${String(detail.location || 'configuration')}: ${String(detail.message || 'Invalid value.')}`;
    })
    .join('\n');
};

interface FieldEditorProps {
  name: string;
  schema: RuleConfigJsonSchema;
  root: RuleConfigJsonSchema;
  value: RuleConfigValue;
  required?: boolean;
  depth?: number;
  onChange: (value: RuleConfigValue) => void;
}

function FieldEditor({ name, schema, root, value, required = false, depth = 0, onChange }: FieldEditorProps) {
  const resolved = resolveRuleConfigSchema(schema, root);
  const label = getRuleConfigFieldLabel(name, resolved);

  if (resolved.enum?.length) {
    return (
      <View className="gap-1.5">
        <Text className="text-xs font-sans-semibold text-text-primary">{label}{required ? ' *' : ''}</Text>
        <View className="flex-row flex-wrap gap-2">
          {resolved.enum.map((option) => {
            const selected = value === option;
            return (
              <Pressable
                key={String(option)}
                onPress={() => onChange(option)}
                className={`rounded-md border px-3 py-2 ${selected ? 'border-primary bg-primary/10' : 'border-border bg-surface'}`}
              >
                <Text className={`text-xs font-sans-medium ${selected ? 'text-primary' : 'text-text-secondary'}`}>{String(option)}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
    );
  }

  if (resolved.type === 'object' || resolved.properties || resolved.additionalProperties) {
    const objectValue = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, RuleConfigValue> : {};
    if (resolved.properties) {
      const content = (
        <View className="gap-3">
          {Object.entries(resolved.properties).map(([childName, childSchema]) => (
            <FieldEditor
              key={childName}
              name={childName}
              schema={childSchema}
              root={root}
              value={objectValue[childName]}
              required={resolved.required?.includes(childName)}
              depth={depth + 1}
              onChange={(nextValue) => onChange({ ...objectValue, [childName]: nextValue })}
            />
          ))}
        </View>
      );
      if (depth === 0) {
        return (
          <Card className="gap-2.5">
            <Text className="text-sm font-sans-bold text-text-primary">{label}{required ? ' *' : ''}</Text>
            {resolved.description && <Text className="text-xs font-sans text-text-muted">{resolved.description}</Text>}
            {content}
          </Card>
        );
      }
      return (
        <View className="gap-2 border-l-2 border-border pl-3">
          <Text className="text-xs font-sans-bold text-text-primary">{label}{required ? ' *' : ''}</Text>
          {content}
        </View>
      );
    }
    return (
      <MapEditor
        label={label}
        schema={typeof resolved.additionalProperties === 'object' ? resolved.additionalProperties : { type: 'string' }}
        root={root}
        value={objectValue}
        required={required}
        onChange={onChange}
      />
    );
  }

  if (resolved.type === 'array') {
    const arrayValue = Array.isArray(value) ? value : [];
    const itemSchema = resolved.items || { type: 'string' };
    return (
      <View className="gap-2 border-l-2 border-border pl-3">
        <View className="flex-row items-center justify-between gap-2">
          <Text className="text-xs font-sans-bold text-text-primary">{label}{required ? ' *' : ''}</Text>
          <Button
            label="Add"
            variant="outline"
            size="sm"
            icon={<Plus size={13} color={COLORS.primary} />}
            onPress={() => onChange([...arrayValue, buildInitialRuleConfigValue(itemSchema, root)])}
          />
        </View>
        {arrayValue.length === 0 && <Text className="text-xs font-sans text-text-faint">No entries added.</Text>}
        {arrayValue.map((item, index) => (
          <View key={`${name}-${index}`} className="rounded-md border border-border p-3 gap-2">
            <View className="flex-row items-center justify-between">
              <Text className="text-[11px] font-sans-semibold text-text-muted">Entry {index + 1}</Text>
              <Pressable onPress={() => onChange(arrayValue.filter((_, itemIndex) => itemIndex !== index))} className="p-1.5">
                <Trash2 size={14} color={COLORS.danger} />
              </Pressable>
            </View>
            <FieldEditor
              name={`${name}_${index + 1}`}
              schema={itemSchema}
              root={root}
              value={item}
              depth={depth + 1}
              onChange={(nextValue) => onChange(arrayValue.map((current, itemIndex) => itemIndex === index ? nextValue : current))}
            />
          </View>
        ))}
      </View>
    );
  }

  if (resolved.type === 'boolean') {
    const selected = value === true;
    return (
      <Pressable onPress={() => onChange(!selected)} className="flex-row items-center gap-2 py-1">
        <View className={`w-5 h-5 rounded border items-center justify-center ${selected ? 'bg-primary border-primary' : 'bg-surface border-border'}`}>
          {selected && <Check size={13} color={COLORS.textInverse} />}
        </View>
        <Text className="text-xs font-sans-medium text-text-primary">{label}{required ? ' *' : ''}</Text>
      </Pressable>
    );
  }

  const numeric = resolved.type === 'number' || resolved.type === 'integer';
  return (
    <View className="gap-1.5">
      <Text className="text-xs font-sans-semibold text-text-primary">{label}{required ? ' *' : ''}</Text>
      {resolved.description && <Text className="text-[11px] font-sans text-text-muted">{resolved.description}</Text>}
      <TextInput
        value={value === undefined || value === null ? '' : String(value)}
        onChangeText={(text) => onChange(numeric && text.trim() !== '' ? Number(text) : text)}
        keyboardType={numeric ? 'numeric' : 'default'}
        autoCapitalize="none"
        className="min-h-[40px] rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-primary"
      />
    </View>
  );
}

interface MapEditorProps {
  label: string;
  schema: RuleConfigJsonSchema;
  root: RuleConfigJsonSchema;
  value: Record<string, RuleConfigValue>;
  required: boolean;
  onChange: (value: RuleConfigValue) => void;
}

function MapEditor({ label, schema, root, value, required, onChange }: MapEditorProps) {
  const [newKey, setNewKey] = useState('');
  const entries = Object.entries(value);
  const addEntry = () => {
    const key = newKey.trim();
    if (!key || Object.prototype.hasOwnProperty.call(value, key)) return;
    onChange({ ...value, [key]: buildInitialRuleConfigValue(schema, root) });
    setNewKey('');
  };
  return (
    <View className="gap-2 border-l-2 border-border pl-3">
      <Text className="text-xs font-sans-bold text-text-primary">{label}{required ? ' *' : ''}</Text>
      {entries.map(([entryKey, entryValue]) => (
        <View key={entryKey} className="rounded-md border border-border p-3 gap-2">
          <View className="flex-row items-center justify-between">
            <Text className="text-xs font-sans-semibold text-primary">{entryKey}</Text>
            <Pressable onPress={() => onChange(Object.fromEntries(entries.filter(([key]) => key !== entryKey)))} className="p-1.5">
              <Trash2 size={14} color={COLORS.danger} />
            </Pressable>
          </View>
          <FieldEditor name={entryKey} schema={schema} root={root} value={entryValue} onChange={(next) => onChange({ ...value, [entryKey]: next })} />
        </View>
      ))}
      <View className="flex-row items-center gap-2">
        <TextInput
          value={newKey}
          onChangeText={setNewKey}
          placeholder="New option key"
          placeholderTextColor={COLORS.textFaint}
          className="flex-1 min-h-[40px] rounded-md border border-border bg-surface px-3 py-2 text-xs text-text-primary"
        />
        <Button label="Add Option" variant="outline" onPress={addEntry} disabled={!newKey.trim()} />
      </View>
    </View>
  );
}

export default function ConfigSetupScreen() {
  usePageTitle('Initial Configuration Setup | AIRIS');
  const router = useRouter();
  const [schema, setSchema] = useState<RuleConfigJsonSchema | null>(null);
  const [draft, setDraft] = useState<Record<string, RuleConfigValue>>({});
  const [systemDefault, setSystemDefault] = useState<Record<string, RuleConfigValue> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([configService.getRuleConfigSchema(), configService.getSystemDefaultConfig()])
      .then(([schemaResponse, defaultResponse]) => {
        setSchema(schemaResponse);
        setSystemDefault(defaultResponse);
        setDraft(defaultResponse);
      })
      .catch((reason: unknown) => setError(getSafeErrorMessage(reason, 'Failed to load configuration options.')))
      .finally(() => setLoading(false));
  }, []);

  const properties = useMemo(() => schema?.properties || {}, [schema]);
  const initialize = async () => {
    setSaving(true);
    setError(null);
    try {
      await configService.initializeConfig(draft);
      router.replace('/config');
    } catch (reason: unknown) {
      setError(getSafeErrorMessage(reason, 'Configuration validation failed.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Engine Configuration', href: '/config' }, { label: 'Initial Setup' }]} />
      <PageHeader title="Initial Configuration Setup" subtitle="Validate and activate the backend-provided system configuration." />
      <ScrollView className="flex-1 px-3" contentContainerStyle={{ paddingBottom: 16 }}>
        <View className="gap-3 py-3">
          <Card className="gap-2">
            <Text className="text-xs font-sans text-text-muted leading-5">
              Review the validated system baseline below. Controls are generated from the backend schema and no bundled JSON profile or test fixture is loaded.
            </Text>
            <View className="flex-row justify-end">
              <Button
                label="Reset to System Default"
                variant="outline"
                size="sm"
                icon={<RotateCcw size={13} color={COLORS.primary} />}
                onPress={() => systemDefault && setDraft(JSON.parse(JSON.stringify(systemDefault)))}
                disabled={!systemDefault || saving}
              />
            </View>
          </Card>

          {error && (
            <Card className="p-3 bg-danger/10 border-danger/30 flex-row items-start gap-2">
              <AlertCircle size={16} color={COLORS.danger} />
              <Text className="text-xs font-sans-medium text-danger flex-1">{error}</Text>
            </Card>
          )}

          {loading && <Text className="text-sm font-sans text-text-muted">Loading configuration options...</Text>}
          {schema && Object.entries(properties).map(([name, fieldSchema]) => (
            <FieldEditor
              key={name}
              name={name}
              schema={fieldSchema}
              root={schema}
              value={draft[name]}
              required={schema.required?.includes(name)}
              onChange={(value) => setDraft((current) => ({ ...current, [name]: value }))}
            />
          ))}

          {schema && (
            <View className="flex-row justify-end gap-2">
              <Button label="Cancel" variant="ghost" onPress={() => router.replace('/config')} disabled={saving} />
              <Button label={saving ? 'Validating and Activating...' : 'Validate and Activate'} onPress={initialize} loading={saving} size="md" />
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
