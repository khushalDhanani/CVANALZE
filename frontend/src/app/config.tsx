import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { Feather } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useMatchConfig } from '@/hooks/useMatchConfig';
import { MatchComponentWeights } from '@/types/api';
import { TextField, Card, Button } from '@/components/ui';

export default function ConfigScreen() {
  const { config, loading, updating, error, refreshConfig, updateConfig } =
    useMatchConfig();

  // Form states
  const [highThreshold, setHighThreshold] = useState<string>('70');
  const [mediumThreshold, setMediumThreshold] = useState<string>('40');
  const [llmWeight, setLlmWeight] = useState<string>('0.15');
  const [maxLlmBoost, setMaxLlmBoost] = useState<string>('15.0');
  const [skipMargin, setSkipMargin] = useState<string>('15.0');
  const [skipCoverage, setSkipCoverage] = useState<string>('0.50');
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
      setSkipMargin(String(config.LLM_SKIP_MARGIN_THRESHOLD ?? '15.0'));
      setSkipCoverage(String(config.LLM_SKIP_COVERAGE_THRESHOLD ?? '0.50'));
      setMandatoryPenalty(String(config.MANDATORY_FAILURE_PENALTY_PER_ITEM));
      if (config.MATCH_COMPONENT_WEIGHTS) {
        setWeights(config.MATCH_COMPONENT_WEIGHTS);
      }
    }
  }, [config]);

  const handleWeightChange = (key: keyof MatchComponentWeights, val: string) => {
    const num = parseFloat(val) || 0;
    setWeights((prev) => ({ ...prev, [key]: num }));
  };

  const handleSave = async () => {
    setSuccessMsg(null);
    try {
      await updateConfig({
        MATCH_HIGH_THRESHOLD: parseFloat(highThreshold),
        MATCH_MEDIUM_THRESHOLD: parseFloat(mediumThreshold),
        LLM_SEMANTIC_WEIGHT: parseFloat(llmWeight),
        MAX_LLM_BOOST: parseFloat(maxLlmBoost),
        LLM_SKIP_MARGIN_THRESHOLD: parseFloat(skipMargin),
        LLM_SKIP_COVERAGE_THRESHOLD: parseFloat(skipCoverage),
        MANDATORY_FAILURE_PENALTY_PER_ITEM: parseFloat(mandatoryPenalty),
        MATCH_COMPONENT_WEIGHTS: weights,
      });
      setSuccessMsg('Matching Engine Configuration saved successfully!');
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err) {
      // Error handled in hook
    }
  };

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);

  return (
    <SafeAreaView className="flex-1 bg-background">
      {/* Sticky Header */}
      <View className="flex-row items-center justify-between px-3 py-2 bg-surface border-b border-border">
        <View>
          <Text className="text-base font-sans-bold text-text-primary">Engine Configuration</Text>
          <Text className="text-[11px] font-sans text-text-muted">
            Customize component weights, LLM boost, and failure penalties
          </Text>
        </View>
        <Button
          label="Reset"
          variant="ghost"
          size="sm"
          onPress={refreshConfig}
        />
      </View>

      <ScrollView className="flex-1 px-3 pt-4">
        {loading ? (
          <View className="py-12 items-center">
            <ActivityIndicator size="large" color="#4F46E5" />
          </View>
        ) : (
          <View className="gap-4 mb-8">
            {successMsg && (
              <Card className="bg-success/10 border-success/30 flex-row items-center justify-center gap-1.5 p-3">
                <Feather name="check-circle" size={14} color="#16A34A" />
                <Text className="text-xs font-sans-semibold text-success">
                  {successMsg}
                </Text>
              </Card>
            )}

            {error && (
              <Card className="bg-danger/10 border-danger/30 p-3">
                <Text className="text-xs font-sans-semibold text-danger">{error}</Text>
              </Card>
            )}

            {/* SECTION 1: Match Thresholds */}
            <Card className="gap-3">
              <Text className="text-xs font-sans-bold text-primary uppercase tracking-wider">
                1. Match Classification Thresholds
              </Text>

              <View className="flex-row gap-3">
                <View className="flex-1">
                  <TextField
                    label="HIGH Threshold (%):"
                    value={highThreshold}
                    onChangeText={setHighThreshold}
                    keyboardType="numeric"
                  />
                </View>
                <View className="flex-1">
                  <TextField
                    label="MEDIUM Threshold (%):"
                    value={mediumThreshold}
                    onChangeText={setMediumThreshold}
                    keyboardType="numeric"
                  />
                </View>
              </View>
            </Card>

            {/* SECTION 2: LLM & Penalty Settings */}
            <Card className="gap-3">
              <Text className="text-xs font-sans-bold text-info uppercase tracking-wider">
                2. LLM Weights & Penalties
              </Text>

              <View className="flex-row gap-3">
                <View className="flex-1">
                  <TextField
                    label="LLM Weight Ratio:"
                    value={llmWeight}
                    onChangeText={setLlmWeight}
                    keyboardType="numeric"
                  />
                </View>

                <View className="flex-1">
                  <TextField
                    label="Max LLM Boost (pts):"
                    value={maxLlmBoost}
                    onChangeText={setMaxLlmBoost}
                    keyboardType="numeric"
                  />
                </View>
              </View>

              <TextField
                label="Mandatory Failure Penalty (pts / item):"
                value={mandatoryPenalty}
                onChangeText={setMandatoryPenalty}
                keyboardType="numeric"
              />
            </Card>

            {/* SECTION 3: LLM Bypass Settings */}
            <Card className="gap-3">
              <Text className="text-xs font-sans-bold text-success uppercase tracking-wider">
                3. LLM Bypass (Fast-Track) Settings
              </Text>

              <View className="flex-row gap-3">
                <View className="flex-1">
                  <TextField
                    label="Margin Threshold (pts):"
                    value={skipMargin}
                    onChangeText={setSkipMargin}
                    keyboardType="numeric"
                  />
                </View>

                <View className="flex-1">
                  <TextField
                    label="Coverage Threshold (ratio):"
                    value={skipCoverage}
                    onChangeText={setSkipCoverage}
                    keyboardType="numeric"
                  />
                </View>
              </View>
            </Card>

            {/* SECTION 4: Component Weights */}
            <Card className="gap-3">
              <View className="flex-row justify-between items-center mb-1">
                <Text className="text-xs font-sans-bold text-warning uppercase tracking-wider">
                  4. Component Score Weights
                </Text>
                <Text
                  className={`text-xs font-sans-bold ${
                    Math.abs(totalWeight - 1.0) < 0.01
                      ? 'text-success'
                      : 'text-danger'
                  }`}
                >
                  Sum: {(totalWeight * 100).toFixed(0)}%
                </Text>
              </View>

              {Object.keys(weights).map((key) => {
                const k = key as keyof MatchComponentWeights;
                return (
                  <View key={k} className="flex-row justify-between items-center bg-background p-2 rounded-sm border border-border">
                    <Text className="text-xs font-sans-medium text-text-primary capitalize">
                      {k}
                    </Text>
                    <View className="w-20">
                      <TextField
                        label=""
                        value={String(weights[k])}
                        onChangeText={(val) => handleWeightChange(k, val)}
                        keyboardType="numeric"
                        style={{ textAlign: 'right', paddingVertical: 4 }}
                      />
                    </View>
                  </View>
                );
              })}
            </Card>

            {/* SAVE BUTTON */}
            <Button
              label={updating ? 'Saving Configuration...' : 'Save Configuration Changes'}
              onPress={handleSave}
              loading={updating}
              disabled={updating}
              size="md"
            />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
