import 'dart:convert';
import 'package:http/http.dart' as http;
import '../utils/platform_utils.dart';

/// Service for REST API calls (clubs, validation, etc.)
class ApiService {
  static ApiService? _instance;
  late final String _baseUrl;

  ApiService._internal() {
    _baseUrl = getApiBaseUrl();
  }

  factory ApiService() {
    _instance ??= ApiService._internal();
    return _instance!;
  }

  /// Get all players for a sport (NBA-only for now — for grid autocomplete).
  Future<List<PlayerInfo>> getPlayers(String sport) async {
    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/players/$sport'),
      );
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final players = data['players'] as List<dynamic>? ?? [];
        return players
            .map((p) => PlayerInfo.fromJson(p as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {
      // Silently fail — typing still works, autocomplete just empty.
    }
    return [];
  }

  /// Get all clubs for a sport
  Future<List<ClubInfo>> getClubs(String sport) async {
    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/clubs/$sport'),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final clubs = data['clubs'] as List<dynamic>;
        return clubs.map((c) => ClubInfo.fromJson(c)).toList();
      }
    } catch (e) {
      // Silently fail - autocomplete will just not work
    }
    return [];
  }

  /// Validate a club name
  Future<ClubValidationResult> validateClub(String sport, String name) async {
    if (name.trim().length < 2) {
      return ClubValidationResult(valid: false, error: 'Name too short');
    }

    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/clubs/$sport/validate?name=${Uri.encodeComponent(name)}'),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return ClubValidationResult.fromJson(data);
      }
    } catch (e) {
      // Network error - allow submission anyway (backend will validate)
      return ClubValidationResult(valid: true, normalizedName: name);
    }

    return ClubValidationResult(valid: false, error: 'Validation failed');
  }
}

/// Lightweight NBA player entry for grid-mode autocomplete.
class PlayerInfo {
  final String name;
  final String? externalId;

  PlayerInfo({required this.name, this.externalId});

  factory PlayerInfo.fromJson(Map<String, dynamic> json) => PlayerInfo(
        name: json['name'] as String,
        externalId: json['external_id'] as String?,
      );

  /// NBA.com headshot URL (null when no external_id).
  String? get headshotUrl => externalId == null
      ? null
      : 'https://cdn.nba.com/headshots/nba/latest/1040x760/$externalId.png';
}

/// Club information from API
class ClubInfo {
  final String fullName;
  final String? nickname;
  final String? abbreviation;
  final String? country;
  final String? logo;
  final String? badge;

  ClubInfo({
    required this.fullName,
    this.nickname,
    this.abbreviation,
    this.country,
    this.logo,
    this.badge,
  });

  factory ClubInfo.fromJson(Map<String, dynamic> json) {
    return ClubInfo(
      fullName: json['full_name'] as String,
      nickname: json['nickname'] as String?,
      abbreviation: json['abbreviation'] as String?,
      country: json['country'] as String?,
      logo: json['logo_small'] as String? ?? json['logo'] as String?,
      badge: json['badge'] as String?,
    );
  }

  /// Get display name (nickname for NBA, full name for soccer)
  String get displayName => nickname ?? fullName;

  /// Get all searchable terms for this club
  List<String> get searchTerms {
    final terms = <String>[fullName.toLowerCase()];
    if (nickname != null) terms.add(nickname!.toLowerCase());
    if (abbreviation != null) terms.add(abbreviation!.toLowerCase());
    return terms;
  }
}

/// Result of club validation
class ClubValidationResult {
  final bool valid;
  final String? normalizedName;
  final String? error;
  final ClubInfo? club;

  ClubValidationResult({
    required this.valid,
    this.normalizedName,
    this.error,
    this.club,
  });

  factory ClubValidationResult.fromJson(Map<String, dynamic> json) {
    ClubInfo? club;
    if (json['club'] != null) {
      club = ClubInfo.fromJson(json['club'] as Map<String, dynamic>);
    }

    return ClubValidationResult(
      valid: json['valid'] as bool,
      normalizedName: json['normalized_name'] as String?,
      error: json['error'] as String?,
      club: club,
    );
  }
}
