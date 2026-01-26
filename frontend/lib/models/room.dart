import 'player.dart';
import 'game_state.dart';

/// Represents a game room
class Room {
  final String code;
  final SportType sport;
  final List<Player> players;
  final GamePhase phase;
  final int roundNumber;
  final DateTime? createdAt;

  const Room({
    required this.code,
    required this.sport,
    this.players = const [],
    this.phase = GamePhase.lobby,
    this.roundNumber = 1,
    this.createdAt,
  });

  bool get isFull => players.length >= 2;
  bool get isEmpty => players.isEmpty;
  int get playerCount => players.length;

  Player? get player1 => players.isNotEmpty ? players[0] : null;
  Player? get player2 => players.length > 1 ? players[1] : null;

  Room copyWith({
    String? code,
    SportType? sport,
    List<Player>? players,
    GamePhase? phase,
    int? roundNumber,
    DateTime? createdAt,
  }) {
    return Room(
      code: code ?? this.code,
      sport: sport ?? this.sport,
      players: players ?? this.players,
      phase: phase ?? this.phase,
      roundNumber: roundNumber ?? this.roundNumber,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  factory Room.fromJson(Map<String, dynamic> json) {
    return Room(
      code: json['code'] as String,
      sport: SportType.fromString(json['sport'] as String? ?? 'soccer'),
      players: (json['players'] as List<dynamic>?)
              ?.map((e) => Player.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      phase: _parsePhase(json['phase'] as String?),
      roundNumber: json['round_number'] as int? ?? 1,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
    );
  }

  static GamePhase _parsePhase(String? phase) {
    switch (phase) {
      case 'lobby':
        return GamePhase.lobby;
      case 'club_selection':
        return GamePhase.clubSelection;
      case 'guessing':
        return GamePhase.guessing;
      case 'results':
        return GamePhase.results;
      default:
        return GamePhase.lobby;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'code': code,
      'sport': sport.apiValue,
      'players': players.map((e) => e.toJson()).toList(),
      'phase': phase.name,
      'round_number': roundNumber,
      'created_at': createdAt?.toIso8601String(),
    };
  }

  @override
  String toString() => 'Room(code: $code, players: ${players.length}, phase: $phase)';
}
