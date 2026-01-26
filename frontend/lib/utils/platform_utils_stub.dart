/// Stub implementation for non-web platforms (mobile, desktop)
/// These always connect to localhost:8000 during development

String getWebSocketUrl() {
  return 'ws://localhost:8000/ws';
}

String getApiBaseUrl() {
  return 'http://localhost:8000';
}
