import 'platform_utils.dart';

/// Convert external image URL to proxied URL for CORS bypass
String? getProxiedImageUrl(String? imageUrl) {
  if (imageUrl == null || imageUrl.isEmpty) return null;
  final baseUrl = getApiBaseUrl();
  return '$baseUrl/api/image/proxy?url=${Uri.encodeComponent(imageUrl)}';
}
