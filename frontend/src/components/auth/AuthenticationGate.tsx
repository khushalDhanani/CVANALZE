import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { LockKeyhole, ServerOff } from 'lucide-react-native';

import { BRAND } from '@/constants/brand';
import { COLORS } from '@/constants/colors';
import { ApiError, apiClient, AuthSession } from '@/services/apiClient';
import { Button, Card, TextField } from '@/components/ui';

interface AuthContextValue {
  authRequired: boolean;
  role: AuthSession['role'];
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthenticationGate.');
  }
  return context;
}

export function AuthenticationGate({ children }: React.PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [checking, setChecking] = useState(true);
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const checkSession = useCallback(async () => {
    setChecking(true);
    setError(null);
    try {
      setSession(await apiClient.getSession());
    } catch (requestError) {
      setSession(null);
      setError(requestError instanceof ApiError && requestError.status === 0
        ? 'Unable to reach the API. Check the configured API URL and try again.'
        : 'Unable to verify your session. Please try again.');
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    apiClient.setUnauthorizedHandler(() => {
      setSession((current) => current ? { ...current, authenticated: false } : current);
    });
    checkSession();
    return () => apiClient.setUnauthorizedHandler(null);
  }, [checkSession]);

  const signIn = async () => {
    const credential = apiKey.trim();
    if (!credential) {
      setError('Enter your recruiter or administrator access key.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      setSession(await apiClient.createSession(credential));
    } catch (requestError) {
      setError(requestError instanceof ApiError && requestError.status === 401
        ? 'The access key is invalid.'
        : 'Unable to sign in. Please try again.');
    } finally {
      setApiKey('');
      setSubmitting(false);
    }
  };

  const signOut = useCallback(async () => {
    try {
      await apiClient.deleteSession();
    } finally {
      setSession((current) => ({
        authenticated: false,
        auth_required: current?.auth_required ?? true,
        role: null,
        expires_in_seconds: null,
      }));
    }
  }, []);

  const contextValue = useMemo(() => ({
    authRequired: session?.auth_required ?? true,
    role: session?.role ?? null,
    signOut,
  }), [session, signOut]);

  if (checking) {
    return (
      <View className="flex-1 items-center justify-center bg-background">
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text className="mt-3 text-sm font-sans text-text-muted">Checking secure session...</Text>
      </View>
    );
  }

  if (!session) {
    return (
      <View className="flex-1 items-center justify-center bg-background px-4">
        <Card className="w-full max-w-md p-6">
          <View className="items-center gap-3 mb-5">
            <View className="w-12 h-12 rounded-full bg-danger/10 items-center justify-center">
              <ServerOff size={24} color={COLORS.danger} />
            </View>
            <View className="items-center gap-1">
              <Text className="text-xl font-sans-bold text-text-primary">Unable to reach the API</Text>
              <Text className="text-sm font-sans text-text-muted text-center">
                {error || 'Check that the backend is running and try again.'}
              </Text>
            </View>
          </View>
          <Button label="Retry connection" size="lg" onPress={checkSession} />
        </Card>
      </View>
    );
  }

  if (!session?.authenticated) {
    return (
      <View className="flex-1 items-center justify-center bg-background px-4">
        <Card className="w-full max-w-md p-6">
          <View className="items-center gap-3 mb-5">
            <View className="w-12 h-12 rounded-full bg-primary/10 items-center justify-center">
              <LockKeyhole size={24} color={COLORS.primary} />
            </View>
            <View className="items-center gap-1">
              <Text className="text-xl font-sans-bold text-text-primary">Sign in to {BRAND.name}</Text>
              <Text className="text-sm font-sans text-text-muted text-center">
                Use your issued recruiter or administrator access key. It is exchanged for a short-lived secure session and is not stored by this app.
              </Text>
            </View>
          </View>
          <View className="gap-4">
            <TextField
              label="Access key"
              value={apiKey}
              onChangeText={setApiKey}
              onSubmitEditing={signIn}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              textContentType="password"
              error={error ?? undefined}
            />
            <Button label="Sign in" size="lg" onPress={signIn} loading={submitting} />
          </View>
        </Card>
      </View>
    );
  }

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}
