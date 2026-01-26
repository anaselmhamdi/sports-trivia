import 'package:flutter/foundation.dart' show kIsWeb;
import 'platform_utils_stub.dart'
    if (dart.library.html) 'platform_utils_web.dart' as platform;

/// Get WebSocket URL dynamically based on current host
/// - Development: connects to localhost:8000
/// - Production: connects to same origin
String getWebSocketUrl() {
  if (kIsWeb) {
    return platform.getWebSocketUrl();
  }
  // Native/development: use localhost
  return 'ws://localhost:8000/ws';
}

/// Get base HTTP URL for API calls
/// - Development: connects to localhost:8000
/// - Production: connects to same origin
String getApiBaseUrl() {
  if (kIsWeb) {
    return platform.getApiBaseUrl();
  }
  // Native/development: use localhost
  return 'http://localhost:8000';
}
