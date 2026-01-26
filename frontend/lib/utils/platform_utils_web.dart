import 'dart:html' as html;

/// Web implementation - uses browser location
/// In production (same origin), connects to current host
/// In development (localhost on different port), connects to backend on port 8000
String getWebSocketUrl() {
  final location = html.window.location;
  final protocol = location.protocol == 'https:' ? 'wss:' : 'ws:';

  // Check if we're in local development (Flutter dev server on different port)
  if (location.hostname == 'localhost' || location.hostname == '127.0.0.1') {
    // In development, backend is always on port 8000
    return 'ws://${location.hostname}:8000/ws';
  }

  // In production, frontend and backend are on the same origin
  return '$protocol//${location.host}/ws';
}

/// Get base HTTP URL for API calls
String getApiBaseUrl() {
  final location = html.window.location;
  final protocol = location.protocol;

  // Check if we're in local development
  if (location.hostname == 'localhost' || location.hostname == '127.0.0.1') {
    return 'http://${location.hostname}:8000';
  }

  return '$protocol//${location.host}';
}
