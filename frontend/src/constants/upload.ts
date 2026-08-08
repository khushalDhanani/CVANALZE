export const SUPPORTED_RESUME_FORMATS = {
  extensions: ['.pdf', '.docx', '.doc', '.txt'] as const,
  mimeTypes: [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
  ],
  label: 'PDF, DOCX, DOC, or TXT (up to 10MB)',
  accept: '.pdf,.doc,.docx,.txt',
  maxSizeBytes: 10 * 1024 * 1024, // 10MB
};
