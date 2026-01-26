import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/game_state.dart';
import '../services/websocket_service.dart';
import '../utils/platform_utils.dart';
import 'game_orchestrator.dart';

/// Provider for the WebSocket service (singleton)
final websocketServiceProvider = Provider<WebSocketService>((ref) {
  final service = WebSocketService();
  ref.onDispose(() => service.dispose());
  return service;
});

/// Provider for the game state
final gameStateProvider = StateNotifierProvider<GameNotifier, GameState>((ref) {
  final wsService = ref.watch(websocketServiceProvider);
  return GameNotifier(wsService);
});

/// Notifier that bridges WebSocket events to UI state.
/// The backend is the source of truth - this just reflects what it tells us.
class GameNotifier extends StateNotifier<GameState> {
  final WebSocketService _ws;
  final GameOrchestrator _orchestrator = const GameOrchestrator();
  final List<StreamSubscription> _subscriptions = [];

  GameNotifier(this._ws) : super(GameState.initial) {
    _subscribeToBackendEvents();
  }

  /// Subscribe to all backend events and update local state accordingly
  void _subscribeToBackendEvents() {
    // Connection status
    _subscribe(_ws.connectionState, (status) {
      final wasReconnecting = state.isReconnecting;
      state = _orchestrator.onConnectionStatusChanged(state, status);

      // Auto-request state sync on reconnection
      if (status == ConnectionStatus.connected && wasReconnecting && state.roomCode != null) {
        _ws.syncState();
      }
    });

    // Room created (we created a room, now waiting for opponent)
    _subscribe(_ws.onRoomCreated, (e) {
      state = _orchestrator.onRoomCreated(
        current: state,
        roomCode: e.roomCode,
        self: e.player,
        sport: e.sport,
        mode: e.mode,
        maxPlayers: e.maxPlayers,
        hostId: e.hostId,
      );
    });

    // Room joined (we joined an existing room)
    _subscribe(_ws.onRoomJoined, (e) {
      state = _orchestrator.onRoomJoined(
        current: state,
        roomCode: e.roomCode,
        self: e.self,
        opponent: e.opponent,
        allPlayers: e.players,
        sport: e.sport,
        mode: e.mode,
        maxPlayers: e.maxPlayers,
        hostId: e.hostId,
        phase: e.phase,
        poolSize: e.poolSize,
      );
    });

    // Opponent joined our room
    _subscribe(_ws.onPlayerJoined, (e) {
      state = _orchestrator.onOpponentJoined(state, e.player, e.phase);
    });

    // Player left
    _subscribe(_ws.onPlayerLeft, (e) {
      state = _orchestrator.onPlayerLeft(
        state,
        e.playerId,
        newHostId: e.newHostId,
        updatedPlayers: e.players.isNotEmpty ? e.players : null,
      );
    });

    // Someone submitted a club
    _subscribe(_ws.onClubSubmitted, (e) {
      state = _orchestrator.onClubSubmittedByPlayer(state, e.playerId);
    });

    // Clubs have no common players - need to resubmit
    _subscribe(_ws.onClubsInvalid, (e) {
      state = _orchestrator.onClubsInvalid(state, e.error);
    });

    // Both clubs submitted, guessing phase starts
    _subscribe(_ws.onGuessingStarted, (e) {
      state = _orchestrator.onGuessingStarted(
        current: state,
        club1: e.club1,
        club2: e.club2,
        club1Logo: e.club1Info?.logoUrl,
        club2Logo: e.club2Info?.logoUrl,
        clubs: e.clubs,
        clubLogos: e.clubInfoList.map((c) => c.logoUrl).toList(),
        deadline: e.deadline,
        validAnswerCount: e.validAnswerCount,
      );
    });

    // Multiplayer: Game started by host
    _subscribe(_ws.onGameStarted, (e) {
      state = _orchestrator.onGameStarted(state, e.phase);
    });

    // Multiplayer: Pool updated
    _subscribe(_ws.onPoolUpdated, (e) {
      state = _orchestrator.onPoolUpdated(state, e.playerId, e.club, e.poolSize);
    });

    // Multiplayer: Selection failed
    _subscribe(_ws.onSelectionFailed, (e) {
      state = _orchestrator.onSelectionFailed(state, e.error, poolCleared: e.poolCleared);
    });

    // Guess result feedback
    _subscribe(_ws.onGuessResult, (e) {
      if (!e.correct) {
        state = _orchestrator.onWrongGuess(state);
        // Clear error after animation
        Future.delayed(const Duration(milliseconds: 500), () {
          if (mounted) {
            state = _orchestrator.onClearError(state);
          }
        });
      }
    });

    // Round ended (someone won or timeout)
    _subscribe(_ws.onRoundEnded, (e) {
      // Convert PlayerAnswerDetail to PlayerAnswer model
      final validAnswerDetails = e.validAnswerDetails
          .map((d) => PlayerAnswer(name: d.name, imageUrl: d.imageUrl))
          .toList();

      state = _orchestrator.onRoundEnded(
        current: state,
        winnerId: e.winnerId,
        winningAnswer: e.winningAnswer,
        winningAnswerImage: e.winningAnswerImage,
        points: e.points,
        validAnswers: e.validAnswers,
        validAnswerDetails: validAnswerDetails,
        scores: e.scores,
      );
    });

    // Error from backend
    _subscribe(_ws.onError, (e) {
      state = _orchestrator.onError(state, e.message);
    });

    // New round started (after play_again)
    _subscribe(_ws.onNewRound, (e) {
      state = _orchestrator.onNewRoundFromServer(state);
    });

    // Full state sync (reconnection)
    _subscribe(_ws.onStateSync, (e) {
      state = _orchestrator.onStateSync(
        current: state,
        version: e.version,
        roomCode: e.roomCode,
        sport: e.sport,
        mode: e.mode,
        maxPlayers: e.maxPlayers,
        hostId: e.hostId,
        phase: e.phase,
        myClub: e.myClub,
        opponentClub: e.opponentClub,
        deadline: e.deadline,
        validAnswerCount: e.validAnswerCount,
        selfPlayer: e.selfPlayer,
        opponent: e.opponent,
        allPlayers: e.allPlayers,
        poolSize: e.poolSize,
        selectedClubs: e.selectedClubs,
        clubsPerRound: e.clubsPerRound,
      );
    });
  }

  /// Helper to subscribe and track subscriptions
  void _subscribe<T>(Stream<T> stream, void Function(T) handler) {
    _subscriptions.add(stream.listen(handler));
  }

  // ============================================================================
  // ACTIONS - Send requests to backend
  // ============================================================================

  /// Connect to game server
  Future<void> connect() async {
    if (state.connectionStatus == ConnectionStatus.connected) return;
    await _ws.connect(getWebSocketUrl());
  }

  /// Create a new room
  Future<void> createRoom(String playerName, SportType sport, {GameMode mode = GameMode.classic, int maxPlayers = 2}) async {
    await connect();
    state = _orchestrator.onSportChanged(state, sport);
    state = _orchestrator.onModeChanged(state, mode);
    _ws.createRoom(playerName, sport, mode: mode, maxPlayers: maxPlayers);
  }

  /// Join an existing room
  Future<void> joinRoom(String roomCode, String playerName) async {
    await connect();
    _ws.joinRoom(roomCode, playerName);
  }

  /// Submit our club choice
  void submitClub(String clubName) {
    // Optimistic update for UI responsiveness
    state = _orchestrator.onClubSubmittedLocally(state, clubName);
    _ws.submitClub(clubName);
  }

  /// Submit a guess
  void submitGuess(String playerName) {
    _ws.submitGuess(playerName);
  }

  /// Request new round
  void playAgain() {
    state = _orchestrator.onPlayAgain(state);
    _ws.playAgain();
  }

  /// Leave current room
  void leaveRoom() {
    _ws.leaveRoom();
    state = _orchestrator.onLeaveRoom(state);
  }

  /// Change sport selection (before creating room)
  void setSport(SportType sport) {
    state = _orchestrator.onSportChanged(state, sport);
  }

  /// Change mode selection (before creating room)
  void setMode(GameMode mode) {
    state = _orchestrator.onModeChanged(state, mode);
  }

  /// Start game (multiplayer, host only)
  void startGame() {
    _ws.startGame();
  }

  /// Start round (multiplayer, host only)
  void startRound({int clubsPerRound = 2}) {
    _ws.startRound(clubsPerRound: clubsPerRound);
  }

  /// Clear error message
  void clearError() {
    state = _orchestrator.onClearError(state);
  }

  /// Request full state sync from server (e.g., after reconnect)
  void syncState() {
    _ws.syncState();
  }

  @override
  void dispose() {
    for (final sub in _subscriptions) {
      sub.cancel();
    }
    super.dispose();
  }
}

// ============================================================================
// DERIVED PROVIDERS
// ============================================================================

/// Remaining time in seconds (updates every second during guessing phase)
final remainingTimeProvider = StreamProvider<int>((ref) {
  final gameState = ref.watch(gameStateProvider);

  if (gameState.deadline == null || gameState.phase != GamePhase.guessing) {
    return Stream.value(0);
  }

  return Stream.periodic(const Duration(seconds: 1), (_) {
    final remaining = gameState.deadline!.difference(DateTime.now()).inSeconds;
    return remaining > 0 ? remaining : 0;
  });
});

/// Timer urgency level: 0 = calm (>30s), 1 = warning (15-30s), 2 = urgent (<15s)
final timerUrgencyProvider = Provider<int>((ref) {
  final timeAsync = ref.watch(remainingTimeProvider);
  return timeAsync.when(
    data: (time) {
      if (time > 30) return 0;
      if (time > 15) return 1;
      return 2;
    },
    loading: () => 0,
    error: (_, __) => 0,
  );
});

/// Whether we're waiting for opponent to join
final isWaitingForOpponentProvider = Provider<bool>((ref) {
  final state = ref.watch(gameStateProvider);
  return state.phase == GamePhase.lobby && state.opponent == null;
});

/// Whether both players have submitted clubs
final bothClubsSubmittedProvider = Provider<bool>((ref) {
  final state = ref.watch(gameStateProvider);
  return (state.self?.hasSubmittedClub ?? false) &&
      (state.opponent?.hasSubmittedClub ?? false);
});

/// Whether we won the current round
final didWinRoundProvider = Provider<bool>((ref) {
  final state = ref.watch(gameStateProvider);
  return state.roundResult?.winnerId == state.self?.id;
});

/// Current score difference (positive = winning)
final scoreDifferenceProvider = Provider<int>((ref) {
  final state = ref.watch(gameStateProvider);
  return (state.self?.score ?? 0) - (state.opponent?.score ?? 0);
});
