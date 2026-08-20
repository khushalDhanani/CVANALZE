export interface UploadCapabilities {
  extensions: string[];
  mime_types: Record<string, string[]>;
  max_size_bytes: number;
  max_pdf_pages: number;
  max_files_per_selection: number;
}

export interface BatchCapabilities {
  limit_options: number[];
  default_limit: number;
  max_limit: number;
}

export interface PollingCapabilities {
  interval_ms: number;
  max_attempts: number;
}

export interface ImplementationCapabilities {
  document_parser: string;
  ocr_engine: string;
  llm_provider: string;
  vector_store: string;
}

export interface PipelineStageCapability {
  id: string;
  label: string;
  description: string;
}

export interface ApplicationCapabilities {
  upload: UploadCapabilities;
  batch: BatchCapabilities;
  polling: PollingCapabilities;
  implementation: ImplementationCapabilities;
  pipeline: PipelineStageCapability[];
}
