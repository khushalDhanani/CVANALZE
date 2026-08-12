import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { CheckCircle2, AlertTriangle, AlertCircle, ListChecks } from 'lucide-react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useMatchConfig } from '@/hooks/useMatchConfig';
import { usePageTitle } from '@/hooks/usePageTitle';
import { MatchComponentWeights } from '@/types/api';
import { Card, Button, TextField, WeightControlRow, Breadcrumbs, Badge } from '@/components/ui';
import { COLORS } from '@/constants/colors';

const formatRuleLabel = (value: string): string => {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
};

const formatRuleValue = (value: string | number | null, conditionCount: number): string => {
  if (value !== null && value !== '') return String(value);
  if (conditionCount > 0) return `${conditionCount} condition${conditionCount === 1 ? '' : 's'}`;
  return 'Configured';
};

export default function ConfigScreen() {
  usePageTitle('Engine Configuration | AIRIS');
  const router = useRouter();
  const {
    config,
    loading,
    refreshing,
    updating,
    configurationMissing,
    ruleInventory,
    ruleInventoryError,
    error,
    refreshConfig,
    updateConfig,
  } = useMatchConfig();

  // Form states
  const [highThreshold, setHighThreshold] = useState<string>('70');
  const [mediumThreshold, setMediumThreshold] = useState<string>('40');
  const [llmWeight, setLlmWeight] = useState<string>('0.15');
  const [maxLlmBoost, setMaxLlmBoost] = useState<string>('15.0');
  const [mandatoryPenalty, setMandatoryPenalty] = useState<string>('20.0');
  const [weights, setWeights] = useState<MatchComponentWeights>({
    role: 0.15,
    skills: 0.25,
    experience: 0.15,
    education: 0.1,
    domain: 0.15,
    technology: 0.1,
    certification: 0.05,
    responsibilities: 0.05,
  });

  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    if (config) {
      setHighThreshold(String(config.MATCH_HIGH_THRESHOLD));
      setMediumThreshold(String(config.MATCH_MEDIUM_THRESHOLD));
      setLlmWeight(String(config.LLM_SEMANTIC_WEIGHT));
      setMaxLlmBoost(String(config.MAX_LLM_BOOST));
      setMandatoryPenalty(String(config.MANDATORY_FAILURE_PENALTY_PER_ITEM));
      if (config.MATCH_COMPONENT_WEIGHTS) {
        setWeights(config.MATCH_COMPONENT_WEIGHTS);
      }
    }
  }, [config]);

  const handleWeightChange = (key: keyof MatchComponentWeights, val: string) => {
    const num = parseFloat(val);
    setWeights((prev) => ({ ...prev, [key]: isNaN(num) ? 0 : num }));
  };

  // Dirty State Calculation
  const isDirty = Boolean(
    config && (
      highThreshold !== String(config.MATCH_HIGH_THRESHOLD) ||
      mediumThreshold !== String(config.MATCH_MEDIUM_THRESHOLD) ||
      llmWeight !== String(config.LLM_SEMANTIC_WEIGHT) ||
      maxLlmBoost !== String(config.MAX_LLM_BOOST) ||
      mandatoryPenalty !== String(config.MANDATORY_FAILURE_PENALTY_PER_ITEM) ||
      JSON.stringify(weights) !== JSON.stringify(config.MATCH_COMPONENT_WEIGHTS || {})
    )
  );

  // Field-level numeric & relationship validations
  const highNum = parseFloat(highThreshold);
  const medNum = parseFloat(mediumThreshold);
  const llmWeightNum = parseFloat(llmWeight);
  const maxBoostNum = parseFloat(maxLlmBoost);
  const penaltyNum = parseFloat(mandatoryPenalty);

  const highError =
    isNaN(highNum) || highNum < 0 || highNum > 100
      ? 'Must be a percentage between 0% and 100%'
      : !isNaN(medNum) && medNum >= highNum
        ? 'Must be strictly greater than Medium Threshold'
        : undefined;

  const medError =
    isNaN(medNum) || medNum < 0 || medNum > 100
      ? 'Must be a percentage between 0% and 100%'
      : !isNaN(highNum) && medNum >= highNum
        ? 'Must be strictly less than High Threshold'
        : undefined;

  const llmWeightError =
    isNaN(llmWeightNum) || llmWeightNum < 0 || llmWeightNum > 1
      ? 'Must be a ratio between 0.00 and 1.00'
      : undefined;

  const maxBoostError =
    isNaN(maxBoostNum) || maxBoostNum < 0 || maxBoostNum > 50
      ? 'Must be between 0.0 and 50.0 points'
      : undefined;

  const penaltyError =
    isNaN(penaltyNum) || penaltyNum < 0
      ? 'Must be a non-negative number'
      : undefined;

  // Single shared weight sum validity predicate (<0.001 delta)
  const totalWeight = Object.values(weights).reduce((a, b) => a + (isNaN(b) ? 0 : b), 0);
  const isWeightValid = Math.abs(totalWeight - 1.0) < 0.001;

  const isFormValid =
    isWeightValid &&
    !highError &&
    !medError &&
    !llmWeightError &&
    !maxBoostError &&
    !penaltyError;

  const handleSave = async () => {
    setSuccessMsg(null);
    if (!isFormValid || !isDirty) {
      return;
    }
    try {
      await updateConfig({
        MATCH_HIGH_THRESHOLD: highNum,
        MATCH_MEDIUM_THRESHOLD: medNum,
        LLM_SEMANTIC_WEIGHT: llmWeightNum,
        MAX_LLM_BOOST: maxBoostNum,
        MANDATORY_FAILURE_PENALTY_PER_ITEM: penaltyNum,
        MATCH_COMPONENT_WEIGHTS: weights,
      });
      setSuccessMsg('Matching Engine Configuration saved successfully!');
      setTimeout(() => setSuccessMsg(null), 3500);
    } catch (err) {
      // Error handled in hook
    }
  };

  return (
    <SafeAreaView className="flex-1 bg-background">
      <Breadcrumbs items={[{ label: 'Engine Configuration' }]} />

      {/* Sticky Header */}
      <View className="flex-col sm:flex-row items-start sm:items-center justify-between px-3 py-2.5 bg-surface border-b border-border gap-2">
        <View className="flex-row items-center gap-2">
          <View>
            <View className="flex-row items-center gap-2">
              <Text className="text-base font-sans-bold text-text-primary">Engine Configuration</Text>
              <Badge
                label={configurationMissing ? 'Configuration Required' : isDirty ? 'Unsaved Changes' : 'Synced with Server'}
                tone={configurationMissing || isDirty ? 'warning' : 'neutral'}
              />
            </View>
            <Text className="text-[11px] font-sans text-text-muted">
              Customize component weights, LLM boost, and failure penalties
            </Text>
          </View>
        </View>
        <View className="flex-row items-center gap-2 self-stretch sm:self-auto justify-end">
          <Button
            label={isDirty ? 'Discard Changes' : 'Reload Config'}
            variant="ghost"
            size="sm"
            onPress={refreshConfig}
            loading={refreshing}
            disabled={loading || refreshing}
          />
        </View>
      </View>

      <ScrollView className="flex-1 px-3 pt-4">
        {loading ? (
          <View className="py-16 items-center">
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text className="text-xs font-sans text-text-muted mt-2">
              Loading matching engine configuration...
            </Text>
          </View>
        ) : (
          <View className="gap-4 mb-8">
            {successMsg && (
              <Card className="bg-success/10 border-success/30 flex-row items-center justify-center gap-1.5 p-3">
                <CheckCircle2 size={14} color={COLORS.success} />
                <Text className="text-xs font-sans-semibold text-success">
                  {successMsg}
                </Text>
              </Card>
            )}

            {error && (
              <Card className="bg-danger/10 border-danger/30 flex-row items-center gap-1.5 p-3">
                <AlertCircle size={14} color={COLORS.danger} />
                <Text className="text-xs font-sans-semibold text-danger flex-1">{error}</Text>
              </Card>
            )}

            {configurationMissing && (
              <Card className="bg-warning/10 border-warning/30 p-3 flex-row items-center gap-2">
                <AlertTriangle size={16} color={COLORS.warning} />
                <Text className="text-xs font-sans-medium text-warning flex-1">
                  No active profile exists. Use the structured setup wizard to configure every required rule before activation.
                </Text>
              </Card>
            )}

            {ruleInventoryError && (
              <Card className="bg-warning/10 border-warning/30 p-3 flex-row items-center gap-2">
                <AlertTriangle size={16} color={COLORS.warning} />
                <Text className="text-xs font-sans-medium text-warning flex-1">{ruleInventoryError}</Text>
              </Card>
            )}

            {/* SECTION 1: Match Thresholds */}
            <Card className="p-3.5 gap-3.5 shadow-none border-border">
              <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
                1. Match Classification Thresholds
              </Text>

              <View className="flex-col sm:flex-row gap-3">
                <View className="flex-1">
                  <TextField
                    label="HIGH Threshold (%):"
                    value={highThreshold}
                    onChangeText={setHighThreshold}
                    keyboardType="numeric"
                    error={highError}
                    helperText="Minimum score for HIGH recommendation tier"
                  />
                </View>
                <View className="flex-1">
                  <TextField
                    label="MEDIUM Threshold (%):"
                    value={mediumThreshold}
                    onChangeText={setMediumThreshold}
                    keyboardType="numeric"
                    error={medError}
                    helperText="Minimum score for MEDIUM recommendation tier"
                  />
                </View>
              </View>
            </Card>

            {/* SECTION 2: LLM & Penalty Settings */}
            <Card className="p-3.5 gap-3.5 shadow-none border-border">
              <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
                2. LLM Weights & Penalties
              </Text>

              <View className="flex-col sm:flex-row gap-3">
                <View className="flex-1">
                  <TextField
                    label="LLM Semantic Weight Ratio:"
                    value={llmWeight}
                    onChangeText={setLlmWeight}
                    keyboardType="numeric"
                    error={llmWeightError}
                    helperText="Weight of LLM reasoning in final score (0.00 to 1.00)"
                  />
                </View>

                <View className="flex-1">
                  <TextField
                    label="Max LLM Boost (pts):"
                    value={maxLlmBoost}
                    onChangeText={setMaxLlmBoost}
                    keyboardType="numeric"
                    error={maxBoostError}
                    helperText="Maximum score uplift from LLM evaluation"
                  />
                </View>
              </View>

              <TextField
                label="Mandatory Failure Penalty (pts / item):"
                value={mandatoryPenalty}
                onChangeText={setMandatoryPenalty}
                keyboardType="numeric"
                error={penaltyError}
                helperText="Score deduction for each unmet mandatory qualification"
              />
            </Card>

            {/* SECTION 3: Component Weights */}
            <Card className="p-3.5 gap-3.5 shadow-none border-border">
              <View className="flex-row justify-between items-center mb-1">
                <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
                  3. Component Score Weights
                </Text>
                <Text
                  className={`text-xs font-sans-bold ${
                    isWeightValid ? 'text-success' : 'text-danger'
                  }`}
                >
                  Sum: {(totalWeight * 100).toFixed(0)}%
                </Text>
              </View>

              {Object.keys(weights).map((key) => {
                const k = key as keyof MatchComponentWeights;
                return (
                  <WeightControlRow
                    key={k}
                    label={k}
                    value={String(weights[k])}
                    onChange={(val) => handleWeightChange(k, val)}
                  />
                );
              })}
            </Card>

            {ruleInventory && (
              <Card className="p-3.5 gap-3.5 shadow-none border-border">
                <View className="flex-row items-center justify-between gap-2">
                  <View className="flex-row items-center gap-2">
                    <ListChecks size={16} color={COLORS.primary} />
                    <Text className="text-xs font-sans-bold text-text-primary uppercase tracking-wider">
                      4. Active Rule List
                    </Text>
                  </View>
                  <Badge label={`${ruleInventory.total_rules} Rules`} tone="neutral" />
                </View>
                <Text className="text-[11px] font-sans text-text-muted">
                  Active profile: {ruleInventory.profile_version}. This inventory is reconstructed from normalized PostgreSQL records.
                </Text>

                {ruleInventory.groups.map((group) => (
                  <View key={`${group.component_type}-${group.component_name}`} className="rounded-md border border-border overflow-hidden">
                    <View className="flex-row items-center justify-between gap-2 bg-background px-3 py-2 border-b border-border">
                      <View className="flex-1">
                        <Text className="text-xs font-sans-semibold text-text-primary">{formatRuleLabel(group.component_name)}</Text>
                        <Text className="text-[10px] font-sans text-text-muted">{formatRuleLabel(group.component_type)}</Text>
                      </View>
                      <Badge label={`${group.rules.length}`} tone="neutral" />
                    </View>
                    {group.rules.map((rule, index) => (
                      <View
                        key={rule.id}
                        className={`px-3 py-2 gap-1 ${index < group.rules.length - 1 ? 'border-b border-border' : ''}`}
                      >
                        <View className="flex-row items-center justify-between gap-2">
                          <Text className="text-xs font-sans-medium text-text-primary flex-1">{formatRuleLabel(rule.name)}</Text>
                          <Badge label={formatRuleLabel(rule.kind)} tone="neutral" />
                        </View>
                        <Text className="text-[10px] font-sans text-text-muted" numberOfLines={2}>
                          {rule.rule_type ? `${formatRuleLabel(rule.rule_type)} · ` : ''}
                          {formatRuleValue(rule.value, rule.condition_count)}
                        </Text>
                      </View>
                    ))}
                  </View>
                ))}
              </Card>
            )}

            {/* SAVE BUTTON & VALIDATION WARNING */}
            {!isWeightValid && (
              <Card className="bg-danger/10 border-danger/30 p-3 flex-row items-center gap-2">
                <AlertTriangle size={16} color={COLORS.danger} />
                <Text className="text-xs font-sans-medium text-danger flex-1">
                  Component weights total must equal exactly 100% (1.00) before saving. Current total is{' '}
                  {(totalWeight * 100).toFixed(0)}%.
                </Text>
              </Card>
            )}

            <Button
              label={
                updating
                  ? 'Saving Configuration...'
                  : configurationMissing
                    ? 'Create Initial Configuration'
                  : !isDirty
                    ? 'Configuration is Up to Date'
                    : 'Save Configuration Changes'
              }
              onPress={configurationMissing ? () => router.push('/config-setup') : handleSave}
              loading={updating}
              disabled={updating || (!configurationMissing && (!isDirty || !isFormValid))}
              size="md"
            />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
