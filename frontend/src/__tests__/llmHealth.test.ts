import { getAvailableOllamaModelsLabel, getLlmHealthPresentation } from '../utils/llmHealth';

function assertEquals(actual: unknown, expected: unknown): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

const configurationError = {
  status: 'configuration_error',
  error: 'Configured Ollama model is unavailable.',
  model_configured: 'generation-model',
  model_available: false,
  embedding_model_configured: 'embedding-model',
  embedding_model_available: true,
  missing_models: ['generation-model'],
  available_models: ['embedding-model:latest'],
};

assertEquals(getLlmHealthPresentation(configurationError), {
  value: 'CONFIG ERROR',
  detail: 'Missing: generation-model',
  tone: 'warning',
});
assertEquals(getAvailableOllamaModelsLabel(configurationError), 'embedding-model:latest');

assertEquals(getLlmHealthPresentation({ status: 'offline', error: 'Ollama server unreachable' }), {
  value: 'OFFLINE',
  detail: 'Ollama server unreachable',
  tone: 'danger',
});

assertEquals(getLlmHealthPresentation({ status: 'disabled', message: 'LLM matching is disabled in config.' }), {
  value: 'DISABLED',
  detail: 'LLM matching is disabled in config.',
  tone: 'info',
});
