import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../models/game_state.dart';
import '../models/player.dart';

/// WebSocket event types from server
class WsEventType {
  static const String roomCreated = 'room_created';
  static const String roomJoined = 'room_joined';
  static const String playerJoined = 'player_joined';
  static const String playerLeft = 'player_left';
  static const String clubSubmitted = 'club_submitted';
  static const String clubsInvalid = 'clubs_invalid';
  static const String guessingStarted = 'guessing_started';
  static const String guessResult = 'guess_result';
  static const String roundEnded = 'round_ended';
  static const String newRound = 'new_round';
  static const String gameError = 'error';
  static const String pong = 'pong';
  static const String stateSync = 'state_sync';
  // Multiplayer events
  static const String gameStarted = 'game_started';
  static const String poolUpdated = 'pool_updated';
  static const String selectionFailed = 'selection_failed';
}

/// WebSocket action types to server
class WsActionType {
  static const String createRoom = 'create_room';
  static const String joinRoom = 'join_room';
  static const String submitClub = 'submit_club';
  static const String submitGuess = 'submit_guess';
  static const String playAgain = 'play_again';
  static const String leaveRoom = 'leave_room';
  static const String ping = 'ping';
  static const String syncState = 'sync_state';
  // Multiplayer actions
  static const String startGame = 'start_game';
  static const String startRound = 'start_round';
}

/// Event data classes
class RoomCreatedEvent {
  final String roomCode;
  final Player player;
  final SportType sport;
  final GameMode mode;
  final int maxPlayers;
  final String hostId;

  RoomCreatedEvent({
    required this.roomCode,
    required this.player,
    required this.sport,
    required this.mode,
    required this.maxPlayers,
    required this.hostId,
  });

  factory RoomCreatedEvent.fromJson(Map<String, dynamic> json) {
    return RoomCreatedEvent(
      roomCode: json['room_code'] as String,
      player: Player.fromJson(json['player'] as Map<String, dynamic>),
      sport: SportType.fromString(json['sport'] as String? ?? 'soccer'),
      mode: GameMode.fromString(json['mode'] as String? ?? 'classic'),
      maxPlayers: json['max_players'] as int? ?? 2,
      hostId: json['host_id'] as String? ?? '',
    );
  }
}

class RoomJoinedEvent {
  final String roomCode;
  final List<Player> players;
  final SportType sport;
  final GameMode mode;
  final int maxPlayers;
  final String hostId;
  final String phase;
  final int poolSize;

  RoomJoinedEvent({
    required this.roomCode,
    required this.players,
    required this.sport,
    required this.mode,
    required this.maxPlayers,
    required this.hostId,
    required this.phase,
    this.poolSize = 0,
  });

  /// Get self (last player in array is the joining player)
  Player get self => players.last;

  /// Get opponent if exists (for classic mode compatibility)
  Player? get opponent => players.length > 1 ? players.first : null;

  factory RoomJoinedEvent.fromJson(Map<String, dynamic> json) {
    final playersList = (json['players'] as List<dynamic>?)
            ?.map((e) => Player.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    return RoomJoinedEvent(
      roomCode: json['room_code'] as String,
      players: playersList,
      sport: SportType.fromString(json['sport'] as String? ?? 'soccer'),
      mode: GameMode.fromString(json['mode'] as String? ?? 'classic'),
      maxPlayers: json['max_players'] as int? ?? 2,
      hostId: json['host_id'] as String? ?? '',
      phase: json['phase'] as String? ?? 'lobby',
      poolSize: json['pool_size'] as int? ?? 0,
    );
  }
}

class PlayerJoinedEvent {
  final Player player;
  final String phase;

  PlayerJoinedEvent({required this.player, required this.phase});

  factory PlayerJoinedEvent.fromJson(Map<String, dynamic> json) {
    return PlayerJoinedEvent(
      player: Player.fromJson(json['player'] as Map<String, dynamic>),
      phase: json['phase'] as String? ?? 'waiting_for_clubs',
    );
  }
}

class PlayerLeftEvent {
  final String playerId;
  final String? playerName;
  final String? newHostId;
  final List<Player> players;

  PlayerLeftEvent({
    required this.playerId,
    this.playerName,
    this.newHostId,
    this.players = const [],
  });

  factory PlayerLeftEvent.fromJson(Map<String, dynamic> json) {
    final playersList = (json['players'] as List<dynamic>?)
        ?.map((e) => Player.fromJson(e as Map<String, dynamic>))
        .toList() ?? [];
    return PlayerLeftEvent(
      playerId: json['player_id'] as String,
      playerName: json['player_name'] as String?,
      newHostId: json['new_host_id'] as String?,
      players: playersList,
    );
  }
}

class ClubSubmittedEvent {
  final String playerId;

  ClubSubmittedEvent({required this.playerId});

  factory ClubSubmittedEvent.fromJson(Map<String, dynamic> json) {
    return ClubSubmittedEvent(
      playerId: json['player_id'] as String,
    );
  }
}

/// Event when submitted clubs have no common players
class ClubsInvalidEvent {
  final String error;

  ClubsInvalidEvent({required this.error});

  factory ClubsInvalidEvent.fromJson(Map<String, dynamic> json) {
    return ClubsInvalidEvent(
      error: json['error'] as String? ?? 'No common players found',
    );
  }
}

/// Club info with logo
class ClubDetails {
  final String fullName;
  final String? logo;
  final String? badge;
  final String? nickname;
  final String? abbreviation;

  ClubDetails({
    required this.fullName,
    this.logo,
    this.badge,
    this.nickname,
    this.abbreviation,
  });

  factory ClubDetails.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return ClubDetails(fullName: 'Unknown');
    }
    return ClubDetails(
      fullName: json['full_name'] as String? ?? 'Unknown',
      logo: json['logo'] as String? ?? json['logo_small'] as String?,
      badge: json['badge'] as String?,
      nickname: json['nickname'] as String?,
      abbreviation: json['abbreviation'] as String?,
    );
  }

  /// Get the best available logo URL (prefer badge as it's more reliable)
  String? get logoUrl => badge ?? logo;
}

class GuessingStartedEvent {
  final String club1;
  final String club2;
  final ClubDetails? club1Info;
  final ClubDetails? club2Info;
  final List<String> clubs;  // All selected clubs (2-4)
  final List<ClubDetails> clubInfoList;  // Info for all clubs
  final Map<String, String> clubSubmitters;  // club -> playerId who submitted
  final DateTime deadline;
  final int validAnswerCount;
  final int? fallbackClubCount;  // If we fell back to fewer clubs

  GuessingStartedEvent({
    required this.club1,
    required this.club2,
    this.club1Info,
    this.club2Info,
    required this.clubs,
    required this.clubInfoList,
    this.clubSubmitters = const {},
    required this.deadline,
    required this.validAnswerCount,
    this.fallbackClubCount,
  });

  factory GuessingStartedEvent.fromJson(Map<String, dynamic> json) {
    // Backend sends clubs as a tuple/array ["club1", "club2", ...]
    final clubsList = (json['clubs'] as List<dynamic>?)
        ?.map((e) => e as String)
        .toList() ?? [];

    // Backend sends club_info as a tuple/array [{...}, {...}, ...]
    final clubInfoJsonList = json['club_info'] as List<dynamic>?;
    final clubDetailsList = <ClubDetails>[];
    ClubDetails? club1Info;
    ClubDetails? club2Info;
    if (clubInfoJsonList != null) {
      for (final info in clubInfoJsonList) {
        clubDetailsList.add(ClubDetails.fromJson(info as Map<String, dynamic>?));
      }
      if (clubDetailsList.isNotEmpty) {
        club1Info = clubDetailsList[0];
      }
      if (clubDetailsList.length > 1) {
        club2Info = clubDetailsList[1];
      }
    }

    // Parse club submitters (multiplayer)
    final submittersJson = json['club_submitters'] as Map<String, dynamic>?;
    final clubSubmitters = submittersJson?.map(
      (k, v) => MapEntry(k, v as String),
    ) ?? {};

    // Backend sends deadline as Unix timestamp (float)
    final deadlineValue = json['deadline'];
    DateTime deadline;
    if (deadlineValue is num) {
      deadline = DateTime.fromMillisecondsSinceEpoch((deadlineValue * 1000).toInt());
    } else if (deadlineValue is String) {
      deadline = DateTime.parse(deadlineValue);
    } else {
      deadline = DateTime.now().add(const Duration(seconds: 60));
    }

    return GuessingStartedEvent(
      club1: clubsList.isNotEmpty ? clubsList[0] : '',
      club2: clubsList.length > 1 ? clubsList[1] : '',
      club1Info: club1Info,
      club2Info: club2Info,
      clubs: clubsList,
      clubInfoList: clubDetailsList,
      clubSubmitters: clubSubmitters,
      deadline: deadline,
      validAnswerCount: json['valid_count'] as int? ?? 0,
      fallbackClubCount: json['fallback_club_count'] as int?,
    );
  }
}

class GuessResultEvent {
  final bool correct;
  final String playerId;
  final String? guess;

  GuessResultEvent({
    required this.correct,
    required this.playerId,
    this.guess,
  });

  factory GuessResultEvent.fromJson(Map<String, dynamic> json) {
    return GuessResultEvent(
      correct: json['correct'] as bool,
      playerId: json['player_id'] as String? ?? '',
      guess: json['guess'] as String?,
    );
  }
}

/// Player answer with optional image URL
class PlayerAnswerDetail {
  final String name;
  final String? imageUrl;

  PlayerAnswerDetail({required this.name, this.imageUrl});

  factory PlayerAnswerDetail.fromJson(Map<String, dynamic> json) {
    return PlayerAnswerDetail(
      name: json['name'] as String,
      imageUrl: json['image_url'] as String?,
    );
  }
}

class RoundEndedEvent {
  final String? winnerId;
  final String? winningAnswer;
  final String? winningAnswerImage;
  final int? points;
  final List<String> validAnswers;
  final List<PlayerAnswerDetail> validAnswerDetails;
  final Map<String, int> scores;

  RoundEndedEvent({
    this.winnerId,
    this.winningAnswer,
    this.winningAnswerImage,
    this.points,
    required this.validAnswers,
    required this.validAnswerDetails,
    required this.scores,
  });

  bool get hasWinner => winnerId != null;
  bool get isTimeout => winnerId == null;

  factory RoundEndedEvent.fromJson(Map<String, dynamic> json) {
    return RoundEndedEvent(
      winnerId: json['winner_id'] as String?,
      winningAnswer: json['winning_answer'] as String?,
      winningAnswerImage: json['winning_answer_image'] as String?,
      points: json['points'] as int?,
      validAnswers: (json['valid_answers'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      validAnswerDetails: (json['valid_answer_details'] as List<dynamic>?)
              ?.map((e) => PlayerAnswerDetail.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      scores: (json['scores'] as Map<String, dynamic>?)?.map(
            (k, v) => MapEntry(k, v as int),
          ) ??
          {},
    );
  }
}

class GameErrorEvent {
  final String message;
  final String? code;

  GameErrorEvent({required this.message, this.code});

  factory GameErrorEvent.fromJson(Map<String, dynamic> json) {
    return GameErrorEvent(
      message: json['message'] as String? ?? 'Unknown error',
      code: json['code'] as String?,
    );
  }
}

class NewRoundEvent {
  final String phase;
  final int roundNumber;

  NewRoundEvent({required this.phase, required this.roundNumber});

  factory NewRoundEvent.fromJson(Map<String, dynamic> json) {
    return NewRoundEvent(
      phase: json['phase'] as String? ?? 'waiting_for_clubs',
      roundNumber: json['round_number'] as int? ?? 1,
    );
  }
}

/// Multiplayer: Game started by host (WAITING_FOR_PLAYERS → WAITING_FOR_CLUBS)
class GameStartedEvent {
  final String phase;
  final String hostId;

  GameStartedEvent({required this.phase, required this.hostId});

  factory GameStartedEvent.fromJson(Map<String, dynamic> json) {
    return GameStartedEvent(
      phase: json['phase'] as String? ?? 'waiting_for_clubs',
      hostId: json['host_id'] as String? ?? '',
    );
  }
}

/// Multiplayer: Club added to pool
class PoolUpdatedEvent {
  final String playerId;
  final String? playerName;
  final String club;
  final int poolSize;

  PoolUpdatedEvent({
    required this.playerId,
    this.playerName,
    required this.club,
    required this.poolSize,
  });

  factory PoolUpdatedEvent.fromJson(Map<String, dynamic> json) {
    return PoolUpdatedEvent(
      playerId: json['player_id'] as String? ?? '',
      playerName: json['player_name'] as String?,
      club: json['club'] as String? ?? '',
      poolSize: json['pool_size'] as int? ?? 0,
    );
  }
}

/// Multiplayer: Selection failed - no common players found
class SelectionFailedEvent {
  final String error;
  final bool poolCleared;

  SelectionFailedEvent({required this.error, this.poolCleared = false});

  factory SelectionFailedEvent.fromJson(Map<String, dynamic> json) {
    return SelectionFailedEvent(
      error: json['error'] as String? ?? 'Could not find clubs with common players',
      poolCleared: json['pool_cleared'] as bool? ?? false,
    );
  }
}

/// Full state sync event for reconnection
class StateSyncEvent {
  final int version;
  final String roomCode;
  final SportType sport;
  final GameMode mode;
  final int maxPlayers;
  final String hostId;
  final String phase;
  final String? myClub;
  final String? opponentClub;
  final DateTime? deadline;
  final int validAnswerCount;
  final Player selfPlayer;
  final Player? opponent;
  final List<Player> allPlayers;
  // Multiplayer-specific
  final int poolSize;
  final List<String> selectedClubs;
  final int clubsPerRound;

  StateSyncEvent({
    required this.version,
    required this.roomCode,
    required this.sport,
    required this.mode,
    required this.maxPlayers,
    required this.hostId,
    required this.phase,
    this.myClub,
    this.opponentClub,
    this.deadline,
    required this.validAnswerCount,
    required this.selfPlayer,
    this.opponent,
    required this.allPlayers,
    this.poolSize = 0,
    this.selectedClubs = const [],
    this.clubsPerRound = 2,
  });

  factory StateSyncEvent.fromJson(Map<String, dynamic> json) {
    // Parse deadline
    DateTime? deadline;
    final deadlineValue = json['deadline'];
    if (deadlineValue is num) {
      deadline = DateTime.fromMillisecondsSinceEpoch((deadlineValue * 1000).toInt());
    }

    // Parse self player
    final selfData = json['self_player'] as Map<String, dynamic>?;
    final selfPlayer = selfData != null
        ? Player(
            id: selfData['id'] as String? ?? '',
            name: selfData['name'] as String? ?? '',
            score: selfData['score'] as int? ?? 0,
            hasSubmittedClub: selfData['submitted'] as bool? ?? false,
          )
        : Player(id: '', name: '');

    // Parse opponent (classic mode)
    Player? opponent;
    final opponentData = json['opponent'] as Map<String, dynamic>?;
    if (opponentData != null) {
      opponent = Player(
        id: opponentData['id'] as String? ?? '',
        name: opponentData['name'] as String? ?? '',
        score: opponentData['score'] as int? ?? 0,
        hasSubmittedClub: opponentData['submitted'] as bool? ?? false,
      );
    }

    // Parse all players list
    final playersList = (json['players'] as List<dynamic>?)
        ?.map((e) => Player.fromJson(e as Map<String, dynamic>))
        .toList() ?? [];

    // Parse selected clubs (multiplayer)
    final selectedClubs = (json['selected_clubs'] as List<dynamic>?)
        ?.map((e) => e as String)
        .toList() ?? [];

    return StateSyncEvent(
      version: json['version'] as int? ?? 0,
      roomCode: json['room_code'] as String? ?? '',
      sport: SportType.fromString(json['sport'] as String? ?? 'soccer'),
      mode: GameMode.fromString(json['mode'] as String? ?? 'classic'),
      maxPlayers: json['max_players'] as int? ?? 2,
      hostId: json['host_id'] as String? ?? '',
      phase: json['phase'] as String? ?? 'waiting_for_players',
      myClub: json['my_club'] as String?,
      opponentClub: json['opponent_club'] as String?,
      deadline: deadline,
      validAnswerCount: json['valid_answer_count'] as int? ?? 0,
      selfPlayer: selfPlayer,
      opponent: opponent,
      allPlayers: playersList,
      poolSize: json['pool_size'] as int? ?? 0,
      selectedClubs: selectedClubs,
      clubsPerRound: json['clubs_per_round'] as int? ?? 2,
    );
  }
}

/// WebSocket service for managing real-time communication
class WebSocketService {
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _pingTimer;

  final _connectionStateController = StreamController<ConnectionStatus>.broadcast();
  final _roomCreatedController = StreamController<RoomCreatedEvent>.broadcast();
  final _roomJoinedController = StreamController<RoomJoinedEvent>.broadcast();
  final _playerJoinedController = StreamController<PlayerJoinedEvent>.broadcast();
  final _playerLeftController = StreamController<PlayerLeftEvent>.broadcast();
  final _clubSubmittedController = StreamController<ClubSubmittedEvent>.broadcast();
  final _clubsInvalidController = StreamController<ClubsInvalidEvent>.broadcast();
  final _guessingStartedController = StreamController<GuessingStartedEvent>.broadcast();
  final _guessResultController = StreamController<GuessResultEvent>.broadcast();
  final _roundEndedController = StreamController<RoundEndedEvent>.broadcast();
  final _newRoundController = StreamController<NewRoundEvent>.broadcast();
  final _errorController = StreamController<GameErrorEvent>.broadcast();
  final _stateSyncController = StreamController<StateSyncEvent>.broadcast();
  // Multiplayer controllers
  final _gameStartedController = StreamController<GameStartedEvent>.broadcast();
  final _poolUpdatedController = StreamController<PoolUpdatedEvent>.broadcast();
  final _selectionFailedController = StreamController<SelectionFailedEvent>.broadcast();

  // Connection state
  Stream<ConnectionStatus> get connectionState => _connectionStateController.stream;

  // Event streams
  Stream<RoomCreatedEvent> get onRoomCreated => _roomCreatedController.stream;
  Stream<RoomJoinedEvent> get onRoomJoined => _roomJoinedController.stream;
  Stream<PlayerJoinedEvent> get onPlayerJoined => _playerJoinedController.stream;
  Stream<PlayerLeftEvent> get onPlayerLeft => _playerLeftController.stream;
  Stream<ClubSubmittedEvent> get onClubSubmitted => _clubSubmittedController.stream;
  Stream<ClubsInvalidEvent> get onClubsInvalid => _clubsInvalidController.stream;
  Stream<GuessingStartedEvent> get onGuessingStarted => _guessingStartedController.stream;
  Stream<GuessResultEvent> get onGuessResult => _guessResultController.stream;
  Stream<RoundEndedEvent> get onRoundEnded => _roundEndedController.stream;
  Stream<NewRoundEvent> get onNewRound => _newRoundController.stream;
  Stream<GameErrorEvent> get onError => _errorController.stream;
  Stream<StateSyncEvent> get onStateSync => _stateSyncController.stream;
  // Multiplayer streams
  Stream<GameStartedEvent> get onGameStarted => _gameStartedController.stream;
  Stream<PoolUpdatedEvent> get onPoolUpdated => _poolUpdatedController.stream;
  Stream<SelectionFailedEvent> get onSelectionFailed => _selectionFailedController.stream;

  bool get isConnected => _channel != null;

  /// Connect to the WebSocket server
  Future<void> connect(String url) async {
    if (_channel != null) {
      debugPrint('WebSocket already connected');
      return;
    }

    try {
      _connectionStateController.add(ConnectionStatus.connecting);
      debugPrint('Connecting to WebSocket: $url');

      _channel = WebSocketChannel.connect(Uri.parse(url));

      _subscription = _channel!.stream.listen(
        _handleMessage,
        onError: _handleError,
        onDone: _handleDone,
      );

      _connectionStateController.add(ConnectionStatus.connected);
      debugPrint('WebSocket connected');

      // Start ping timer to keep connection alive
      _startPingTimer();
    } catch (e) {
      debugPrint('WebSocket connection error: $e');
      _connectionStateController.add(ConnectionStatus.error);
      rethrow;
    }
  }

  /// Disconnect from the WebSocket server
  void disconnect() {
    _stopPingTimer();
    _subscription?.cancel();
    _channel?.sink.close();
    _channel = null;
    _connectionStateController.add(ConnectionStatus.disconnected);
    debugPrint('WebSocket disconnected');
  }

  /// Send a message to the server
  void _send(String event, Map<String, dynamic> data) {
    if (_channel == null) {
      debugPrint('Cannot send message: not connected');
      return;
    }

    final message = jsonEncode({
      'event': event,
      'data': data,
    });

    debugPrint('Sending: $message');
    _channel!.sink.add(message);
  }

  // Outgoing actions
  void createRoom(String playerName, SportType sport, {GameMode mode = GameMode.classic, int maxPlayers = 2}) {
    _send(WsActionType.createRoom, {
      'player_name': playerName,
      'sport': sport.apiValue,
      'mode': mode.apiValue,
      'max_players': maxPlayers,
    });
  }

  void joinRoom(String roomCode, String playerName) {
    _send(WsActionType.joinRoom, {
      'room_code': roomCode.toUpperCase(),
      'player_name': playerName,
    });
  }

  void submitClub(String clubName) {
    _send(WsActionType.submitClub, {
      'club_name': clubName,
    });
  }

  void submitGuess(String playerName) {
    _send(WsActionType.submitGuess, {
      'player_name': playerName,
    });
  }

  void playAgain() {
    _send(WsActionType.playAgain, {});
  }

  void leaveRoom() {
    _send(WsActionType.leaveRoom, {});
  }

  /// Request full state sync from server (e.g., after reconnect)
  void syncState() {
    _send(WsActionType.syncState, {});
  }

  /// Start game (multiplayer, host only)
  void startGame() {
    _send(WsActionType.startGame, {});
  }

  /// Start round (multiplayer, host only)
  void startRound({int clubsPerRound = 2}) {
    _send(WsActionType.startRound, {
      'clubs_per_round': clubsPerRound,
    });
  }

  // Private methods
  void _handleMessage(dynamic message) {
    try {
      debugPrint('Received: $message');
      final json = jsonDecode(message as String) as Map<String, dynamic>;
      final event = json['event'] as String?;
      final data = json['data'] as Map<String, dynamic>? ?? {};

      switch (event) {
        case WsEventType.roomCreated:
          _roomCreatedController.add(RoomCreatedEvent.fromJson(data));
          break;
        case WsEventType.roomJoined:
          _roomJoinedController.add(RoomJoinedEvent.fromJson(data));
          break;
        case WsEventType.playerJoined:
          _playerJoinedController.add(PlayerJoinedEvent.fromJson(data));
          break;
        case WsEventType.playerLeft:
          _playerLeftController.add(PlayerLeftEvent.fromJson(data));
          break;
        case WsEventType.clubSubmitted:
          _clubSubmittedController.add(ClubSubmittedEvent.fromJson(data));
          break;
        case WsEventType.clubsInvalid:
          _clubsInvalidController.add(ClubsInvalidEvent.fromJson(data));
          break;
        case WsEventType.guessingStarted:
          _guessingStartedController.add(GuessingStartedEvent.fromJson(data));
          break;
        case WsEventType.guessResult:
          _guessResultController.add(GuessResultEvent.fromJson(data));
          break;
        case WsEventType.roundEnded:
          _roundEndedController.add(RoundEndedEvent.fromJson(data));
          break;
        case WsEventType.newRound:
          _newRoundController.add(NewRoundEvent.fromJson(data));
          break;
        case WsEventType.gameError:
          _errorController.add(GameErrorEvent.fromJson(data));
          break;
        case WsEventType.pong:
          // Connection is alive
          break;
        case WsEventType.stateSync:
          _stateSyncController.add(StateSyncEvent.fromJson(data));
          break;
        // Multiplayer events
        case WsEventType.gameStarted:
          _gameStartedController.add(GameStartedEvent.fromJson(data));
          break;
        case WsEventType.poolUpdated:
          _poolUpdatedController.add(PoolUpdatedEvent.fromJson(data));
          break;
        case WsEventType.selectionFailed:
          _selectionFailedController.add(SelectionFailedEvent.fromJson(data));
          break;
        default:
          debugPrint('Unknown event type: $event');
      }
    } catch (e) {
      debugPrint('Error parsing message: $e');
      _errorController.add(GameErrorEvent(message: 'Failed to parse server message'));
    }
  }

  void _handleError(dynamic error) {
    debugPrint('WebSocket error: $error');
    _connectionStateController.add(ConnectionStatus.error);
    _errorController.add(GameErrorEvent(message: 'Connection error: $error'));
  }

  void _handleDone() {
    debugPrint('WebSocket connection closed');
    _stopPingTimer();
    _channel = null;
    _connectionStateController.add(ConnectionStatus.disconnected);
  }

  void _startPingTimer() {
    _pingTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (_channel != null) {
        _send(WsActionType.ping, {});
      }
    });
  }

  void _stopPingTimer() {
    _pingTimer?.cancel();
    _pingTimer = null;
  }

  /// Dispose all resources
  void dispose() {
    disconnect();
    _connectionStateController.close();
    _roomCreatedController.close();
    _roomJoinedController.close();
    _playerJoinedController.close();
    _playerLeftController.close();
    _clubSubmittedController.close();
    _clubsInvalidController.close();
    _guessingStartedController.close();
    _guessResultController.close();
    _roundEndedController.close();
    _newRoundController.close();
    _errorController.close();
    _stateSyncController.close();
    // Multiplayer controllers
    _gameStartedController.close();
    _poolUpdatedController.close();
    _selectionFailedController.close();
  }
}
