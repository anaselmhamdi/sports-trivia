import 'player.dart';

/// Represents a player answer with optional image URL
class PlayerAnswer {
  final String name;
  final String? imageUrl;

  const PlayerAnswer({required this.name, this.imageUrl});

  factory PlayerAnswer.fromJson(Map<String, dynamic> json) => PlayerAnswer(
        name: json['name'] as String,
        imageUrl: json['image_url'] as String?,
      );
}

/// Represents the game mode
enum GameMode {
  classic,
  multiplayer;

  String get displayName {
    switch (this) {
      case GameMode.classic:
        return '1v1';
      case GameMode.multiplayer:
        return 'Party';
    }
  }

  String get apiValue {
    switch (this) {
      case GameMode.classic:
        return 'classic';
      case GameMode.multiplayer:
        return 'multiplayer';
    }
  }

  String get description {
    switch (this) {
      case GameMode.classic:
        return '2 players, head to head';
      case GameMode.multiplayer:
        return '2-10 players, shared pool';
    }
  }

  static GameMode fromString(String value) {
    switch (value.toLowerCase()) {
      case 'multiplayer':
        return GameMode.multiplayer;
      default:
        return GameMode.classic;
    }
  }
}

/// Represents the different phases of the game
enum GamePhase {
  home,
  lobby,
  clubSelection,
  guessing,
  results;

  /// Convert backend phase string to enum
  static GamePhase fromBackendString(String value) {
    switch (value.toLowerCase()) {
      case 'lobby':
      case 'waiting_for_players':
        return GamePhase.lobby;
      case 'waiting_for_clubs':
      case 'club_selection':
        return GamePhase.clubSelection;
      case 'guessing':
        return GamePhase.guessing;
      case 'round_end':
      case 'results':
        return GamePhase.results;
      default:
        return GamePhase.home;
    }
  }
}

/// Represents the connection status
enum ConnectionStatus {
  disconnected,
  connecting,
  connected,
  error,
}

/// Represents the sport type
enum SportType {
  nba,
  soccer;

  String get displayName {
    switch (this) {
      case SportType.nba:
        return 'NBA';
      case SportType.soccer:
        return 'Soccer';
    }
  }

  String get apiValue {
    switch (this) {
      case SportType.nba:
        return 'nba';
      case SportType.soccer:
        return 'soccer';
    }
  }

  static SportType fromString(String value) {
    switch (value.toLowerCase()) {
      case 'nba':
        return SportType.nba;
      case 'soccer':
        return SportType.soccer;
      default:
        return SportType.soccer;
    }
  }
}

/// Represents the result of a round
class RoundResult {
  final String? winnerId;
  final String? winnerName;
  final String correctAnswer;
  final String? correctAnswerImageUrl;
  final List<String> validAnswers;
  final List<PlayerAnswer> validAnswerDetails;
  final int pointsEarned;
  final bool isTimeout;

  const RoundResult({
    this.winnerId,
    this.winnerName,
    required this.correctAnswer,
    this.correctAnswerImageUrl,
    this.validAnswers = const [],
    this.validAnswerDetails = const [],
    this.pointsEarned = 0,
    this.isTimeout = false,
  });

  bool get hasWinner => winnerId != null;

  factory RoundResult.fromJson(Map<String, dynamic> json) {
    return RoundResult(
      winnerId: json['winner_id'] as String?,
      winnerName: json['winner_name'] as String?,
      correctAnswer: json['correct_answer'] as String? ?? '',
      correctAnswerImageUrl: json['correct_answer_image_url'] as String?,
      validAnswers: (json['valid_answers'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      validAnswerDetails: (json['valid_answer_details'] as List<dynamic>?)
              ?.map((e) => PlayerAnswer.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      pointsEarned: json['points_earned'] as int? ?? 0,
      isTimeout: json['is_timeout'] as bool? ?? false,
    );
  }
}

/// Main game state model
class GameState {
  final int stateVersion;  // Server state version for stale client detection
  final ConnectionStatus connectionStatus;
  final GamePhase phase;
  final String? roomCode;
  final SportType sport;
  final GameMode mode;
  final int maxPlayers;
  final String? hostId;
  final Player? self;
  final Player? opponent;
  final List<Player> allPlayers;  // All players in multiplayer mode
  final int roundNumber;
  final String? myClub;
  final String? opponentClub;
  final String? myClubLogo;
  final String? opponentClubLogo;
  final List<String> selectedClubs;  // Multiplayer: 2-4 selected clubs
  final List<String?> selectedClubLogos;  // Logos for selected clubs
  final int poolSize;  // Number of clubs in pool
  final int clubsPerRound;  // How many clubs per round (2-4)
  final DateTime? deadline;
  final int validAnswerCount;
  final RoundResult? roundResult;
  final String? errorMessage;
  final bool isCreator;
  final bool isReconnecting;  // Show reconnecting UI instead of resetting

  const GameState({
    this.stateVersion = 0,
    this.connectionStatus = ConnectionStatus.disconnected,
    this.phase = GamePhase.home,
    this.roomCode,
    this.sport = SportType.soccer,
    this.mode = GameMode.classic,
    this.maxPlayers = 2,
    this.hostId,
    this.self,
    this.opponent,
    this.allPlayers = const [],
    this.roundNumber = 1,
    this.myClub,
    this.opponentClub,
    this.myClubLogo,
    this.opponentClubLogo,
    this.selectedClubs = const [],
    this.selectedClubLogos = const [],
    this.poolSize = 0,
    this.clubsPerRound = 2,
    this.deadline,
    this.validAnswerCount = 0,
    this.roundResult,
    this.errorMessage,
    this.isCreator = false,
    this.isReconnecting = false,
  });

  /// Calculate remaining seconds until deadline
  int get remainingSeconds {
    if (deadline == null) return 0;
    final remaining = deadline!.difference(DateTime.now()).inSeconds;
    return remaining > 0 ? remaining : 0;
  }

  /// Check if both players have submitted clubs (classic mode)
  bool get bothClubsSubmitted =>
      (self?.hasSubmittedClub ?? false) && (opponent?.hasSubmittedClub ?? false);

  /// Check if we're waiting for opponent in lobby
  bool get waitingForOpponent => phase == GamePhase.lobby && opponent == null;

  /// Check if this player is the host
  bool get isHost => self?.id == hostId;

  /// Check if we can start the game (multiplayer, host only)
  bool get canStartGame => isHost && allPlayers.length >= 2 && phase == GamePhase.lobby;

  /// Check if we can start a round (multiplayer, host only)
  bool get canStartRound => isHost && poolSize >= 2 && phase == GamePhase.clubSelection;

  /// Whether this is multiplayer mode
  bool get isMultiplayer => mode == GameMode.multiplayer;

  GameState copyWith({
    int? stateVersion,
    ConnectionStatus? connectionStatus,
    GamePhase? phase,
    String? roomCode,
    SportType? sport,
    GameMode? mode,
    int? maxPlayers,
    String? hostId,
    Player? self,
    Player? opponent,
    List<Player>? allPlayers,
    int? roundNumber,
    String? myClub,
    String? opponentClub,
    String? myClubLogo,
    String? opponentClubLogo,
    List<String>? selectedClubs,
    List<String?>? selectedClubLogos,
    int? poolSize,
    int? clubsPerRound,
    DateTime? deadline,
    int? validAnswerCount,
    RoundResult? roundResult,
    String? errorMessage,
    bool? isCreator,
    bool? isReconnecting,
    bool clearOpponent = false,
    bool clearDeadline = false,
    bool clearRoundResult = false,
    bool clearErrorMessage = false,
    bool clearMyClub = false,
    bool clearOpponentClub = false,
    bool clearSelectedClubs = false,
  }) {
    return GameState(
      stateVersion: stateVersion ?? this.stateVersion,
      connectionStatus: connectionStatus ?? this.connectionStatus,
      phase: phase ?? this.phase,
      roomCode: roomCode ?? this.roomCode,
      sport: sport ?? this.sport,
      mode: mode ?? this.mode,
      maxPlayers: maxPlayers ?? this.maxPlayers,
      hostId: hostId ?? this.hostId,
      self: self ?? this.self,
      opponent: clearOpponent ? null : (opponent ?? this.opponent),
      allPlayers: allPlayers ?? this.allPlayers,
      roundNumber: roundNumber ?? this.roundNumber,
      myClub: clearMyClub ? null : (myClub ?? this.myClub),
      opponentClub: clearOpponentClub ? null : (opponentClub ?? this.opponentClub),
      myClubLogo: clearMyClub ? null : (myClubLogo ?? this.myClubLogo),
      opponentClubLogo: clearOpponentClub ? null : (opponentClubLogo ?? this.opponentClubLogo),
      selectedClubs: clearSelectedClubs ? const [] : (selectedClubs ?? this.selectedClubs),
      selectedClubLogos: clearSelectedClubs ? const [] : (selectedClubLogos ?? this.selectedClubLogos),
      poolSize: poolSize ?? this.poolSize,
      clubsPerRound: clubsPerRound ?? this.clubsPerRound,
      deadline: clearDeadline ? null : (deadline ?? this.deadline),
      validAnswerCount: validAnswerCount ?? this.validAnswerCount,
      roundResult: clearRoundResult ? null : (roundResult ?? this.roundResult),
      errorMessage: clearErrorMessage ? null : (errorMessage ?? this.errorMessage),
      isCreator: isCreator ?? this.isCreator,
      isReconnecting: isReconnecting ?? this.isReconnecting,
    );
  }

  /// Initial state
  static const initial = GameState();

  @override
  String toString() {
    return 'GameState(phase: $phase, roomCode: $roomCode, sport: $sport, round: $roundNumber)';
  }
}
