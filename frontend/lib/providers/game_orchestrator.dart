import 'package:flutter/foundation.dart';
import '../models/game_state.dart';
import '../models/player.dart';

/// Orchestrates all game state transitions with clear, named methods.
/// This class is pure - it only computes new states, no side effects.
class GameOrchestrator {
  const GameOrchestrator();

  // ============================================================================
  // CONNECTION
  // ============================================================================

  GameState onConnectionStatusChanged(GameState current, ConnectionStatus status) {
    _log('Connection: $status');

    if (status == ConnectionStatus.disconnected && current.phase != GamePhase.home) {
      // Don't reset to home - keep room context and show reconnecting UI
      // This allows the client to request STATE_SYNC after reconnect
      _log('Disconnected during game -> showing reconnecting UI');
      return current.copyWith(
        connectionStatus: status,
        isReconnecting: true,
      );
    }

    // Clear reconnecting flag when connected
    if (status == ConnectionStatus.connected && current.isReconnecting) {
      return current.copyWith(
        connectionStatus: status,
        isReconnecting: false,
      );
    }

    return current.copyWith(connectionStatus: status);
  }

  // ============================================================================
  // ROOM LIFECYCLE
  // ============================================================================

  GameState onRoomCreated({
    required GameState current,
    required String roomCode,
    required Player self,
    required SportType sport,
    required GameMode mode,
    required int maxPlayers,
    required String hostId,
  }) {
    _log('Room created: $roomCode (${sport.displayName}, ${mode.displayName})');

    return current.copyWith(
      phase: GamePhase.lobby,
      roomCode: roomCode,
      sport: sport,
      mode: mode,
      maxPlayers: maxPlayers,
      hostId: hostId,
      self: self,
      allPlayers: [self],
      isCreator: true,
      roundNumber: 1,
      poolSize: 0,
      clearOpponent: true,
      clearRoundResult: true,
    );
  }

  GameState onRoomJoined({
    required GameState current,
    required String roomCode,
    required Player self,
    required Player? opponent,
    required List<Player> allPlayers,
    required SportType sport,
    required GameMode mode,
    required int maxPlayers,
    required String hostId,
    required String phase,
    int poolSize = 0,
  }) {
    _log('Room joined: $roomCode, players: ${allPlayers.length}, mode: ${mode.displayName}, phase: $phase');

    // Use the phase from the backend - it's the source of truth
    final gamePhase = GamePhase.fromBackendString(phase);

    return current.copyWith(
      phase: gamePhase,
      roomCode: roomCode,
      sport: sport,
      mode: mode,
      maxPlayers: maxPlayers,
      hostId: hostId,
      self: self,
      opponent: opponent,
      allPlayers: allPlayers,
      poolSize: poolSize,
      isCreator: false,
      roundNumber: 1,
    );
  }

  GameState onOpponentJoined(GameState current, Player opponent, String phase) {
    _log('Opponent joined: ${opponent.name}, phase: $phase');

    // Use the phase from the backend - it's the source of truth
    final gamePhase = GamePhase.fromBackendString(phase);

    // Update allPlayers list if the player isn't already in it
    final updatedPlayers = current.allPlayers.any((p) => p.id == opponent.id)
        ? current.allPlayers
        : [...current.allPlayers, opponent];

    return current.copyWith(
      phase: gamePhase,
      opponent: opponent,
      allPlayers: updatedPlayers,
    );
  }

  GameState onPlayerLeft(
    GameState current,
    String playerId, {
    String? newHostId,
    List<Player>? updatedPlayers,
  }) {
    _log('Player left: $playerId${newHostId != null ? ", new host: $newHostId" : ""}');

    // Use the players list from backend if provided, otherwise filter locally
    final players = updatedPlayers ?? current.allPlayers.where((p) => p.id != playerId).toList();

    // Check if the leaving player is the opponent (classic mode)
    final isOpponent = current.opponent?.id == playerId;

    // For classic mode or if we're down to just 1 player, return to lobby
    if (!current.isMultiplayer || players.length < 2) {
      return current.copyWith(
        phase: GamePhase.lobby,
        allPlayers: players,
        hostId: newHostId,
        clearOpponent: isOpponent,
        clearMyClub: true,
        clearOpponentClub: true,
        clearRoundResult: true,
        clearDeadline: true,
      );
    }

    // Multiplayer with enough players remaining - update list and host if needed
    return current.copyWith(
      allPlayers: players,
      hostId: newHostId,
    );
  }

  // Keep for backwards compatibility but delegate to onPlayerLeft
  GameState onOpponentLeft(GameState current) {
    _log('Opponent left -> returning to lobby');

    return current.copyWith(
      phase: GamePhase.lobby,
      clearOpponent: true,
      clearMyClub: true,
      clearOpponentClub: true,
      clearRoundResult: true,
      clearDeadline: true,
    );
  }

  GameState onLeaveRoom(GameState current) {
    _log('Leaving room');
    return _resetToHome(current);
  }

  // ============================================================================
  // MULTIPLAYER SPECIFIC
  // ============================================================================

  GameState onGameStarted(GameState current, String phase) {
    _log('Game started by host -> $phase');
    final gamePhase = GamePhase.fromBackendString(phase);
    return current.copyWith(phase: gamePhase);
  }

  GameState onPoolUpdated(GameState current, String playerId, String club, int poolSize) {
    final isMe = playerId == current.self?.id;
    _log('Pool updated: ${isMe ? "I" : "Player"} added $club, pool size: $poolSize');

    // Update the player's submission status
    GameState newState = current.copyWith(poolSize: poolSize);

    if (isMe) {
      newState = newState.copyWith(
        self: current.self?.copyWith(hasSubmittedClub: true, selectedClub: club),
      );
    } else {
      // Update allPlayers list
      final updatedPlayers = current.allPlayers.map((p) {
        if (p.id == playerId) {
          return p.copyWith(hasSubmittedClub: true);
        }
        return p;
      }).toList();
      newState = newState.copyWith(allPlayers: updatedPlayers);
    }

    return newState;
  }

  GameState onSelectionFailed(GameState current, String error, {bool poolCleared = false}) {
    _log('Selection failed: $error${poolCleared ? " (pool cleared)" : ""}');

    if (poolCleared) {
      // Reset all players' submission status so they can resubmit
      final resetPlayers = current.allPlayers.map((p) {
        return p.copyWith(hasSubmittedClub: false, selectedClub: null);
      }).toList();

      return current.copyWith(
        errorMessage: error,
        phase: GamePhase.clubSelection,
        poolSize: 0,
        self: current.self?.copyWith(hasSubmittedClub: false, selectedClub: null),
        allPlayers: resetPlayers,
      );
    }

    return current.copyWith(
      errorMessage: error,
      phase: GamePhase.clubSelection,
    );
  }

  GameState onModeChanged(GameState current, GameMode mode) {
    _log('Mode changed: ${mode.displayName}');
    return current.copyWith(mode: mode);
  }

  // ============================================================================
  // CLUB SELECTION PHASE
  // ============================================================================

  GameState onClubSubmittedLocally(GameState current, String clubName) {
    _log('Submitting club locally: $clubName');

    return current.copyWith(
      self: current.self?.copyWith(
        hasSubmittedClub: true,
        selectedClub: clubName,
      ),
    );
  }

  GameState onClubSubmittedByPlayer(GameState current, String playerId) {
    final isOpponent = playerId != current.self?.id;
    _log('Club submitted by ${isOpponent ? "opponent" : "self"}');

    if (isOpponent) {
      return current.copyWith(
        opponent: current.opponent?.copyWith(hasSubmittedClub: true),
      );
    } else {
      return current.copyWith(
        self: current.self?.copyWith(hasSubmittedClub: true),
      );
    }
  }

  GameState onClubsInvalid(GameState current, String error) {
    _log('Clubs invalid: $error');

    // Reset both players' club submissions and show error
    return current.copyWith(
      self: current.self?.copyWith(hasSubmittedClub: false, selectedClub: null),
      opponent: current.opponent?.copyWith(hasSubmittedClub: false, selectedClub: null),
      clearMyClub: true,
      clearOpponentClub: true,
      errorMessage: error,
    );
  }

  // ============================================================================
  // GUESSING PHASE
  // ============================================================================

  GameState onGuessingStarted({
    required GameState current,
    required String club1,
    required String club2,
    String? club1Logo,
    String? club2Logo,
    List<String> clubs = const [],
    List<String?> clubLogos = const [],
    required DateTime deadline,
    required int validAnswerCount,
  }) {
    // For multiplayer mode with multiple clubs
    if (current.isMultiplayer && clubs.length > 2) {
      _log('Guessing started (multiplayer): ${clubs.length} clubs, $validAnswerCount answers');
      return current.copyWith(
        phase: GamePhase.guessing,
        selectedClubs: clubs,
        selectedClubLogos: clubLogos,
        // Also set classic fields for compatibility
        myClub: clubs.isNotEmpty ? clubs[0] : null,
        opponentClub: clubs.length > 1 ? clubs[1] : null,
        myClubLogo: clubLogos.isNotEmpty ? clubLogos[0] : null,
        opponentClubLogo: clubLogos.length > 1 ? clubLogos[1] : null,
        deadline: deadline,
        validAnswerCount: validAnswerCount,
        clearErrorMessage: true,
      );
    }

    // CRITICAL: Backend sends the same clubs array to both players.
    // We must match against our locally submitted club to determine which is ours.
    final mySubmittedClub = current.self?.selectedClub?.toLowerCase().trim();

    String myClub;
    String opponentClub;
    String? myClubLogo;
    String? opponentClubLogo;

    if (mySubmittedClub != null && mySubmittedClub.isNotEmpty) {
      final club1Lower = club1.toLowerCase().trim();
      final club2Lower = club2.toLowerCase().trim();

      // Match our submitted club to the clubs array
      if (club1Lower == mySubmittedClub || club1Lower.contains(mySubmittedClub) || mySubmittedClub.contains(club1Lower)) {
        myClub = club1;
        opponentClub = club2;
        myClubLogo = club1Logo;
        opponentClubLogo = club2Logo;
      } else if (club2Lower == mySubmittedClub || club2Lower.contains(mySubmittedClub) || mySubmittedClub.contains(club2Lower)) {
        myClub = club2;
        opponentClub = club1;
        myClubLogo = club2Logo;
        opponentClubLogo = club1Logo;
      } else {
        // Fallback: no match found, use order received (log warning)
        _log('WARNING: Could not match submitted club "$mySubmittedClub" to [$club1, $club2]');
        myClub = club1;
        opponentClub = club2;
        myClubLogo = club1Logo;
        opponentClubLogo = club2Logo;
      }
    } else {
      // No local club recorded - use order received
      _log('WARNING: No local club submission recorded');
      myClub = club1;
      opponentClub = club2;
      myClubLogo = club1Logo;
      opponentClubLogo = club2Logo;
    }

    _log('Guessing started: myClub=$myClub vs opponentClub=$opponentClub ($validAnswerCount answers)');

    return current.copyWith(
      phase: GamePhase.guessing,
      myClub: myClub,
      opponentClub: opponentClub,
      myClubLogo: myClubLogo,
      opponentClubLogo: opponentClubLogo,
      selectedClubs: [myClub, opponentClub],
      selectedClubLogos: [myClubLogo, opponentClubLogo],
      deadline: deadline,
      validAnswerCount: validAnswerCount,
      clearErrorMessage: true,
    );
  }

  GameState onWrongGuess(GameState current) {
    _log('Wrong guess');

    return current.copyWith(
      errorMessage: 'Wrong answer!',
    );
  }

  GameState onClearError(GameState current) {
    return current.copyWith(clearErrorMessage: true);
  }

  // ============================================================================
  // ROUND END
  // ============================================================================

  GameState onRoundEnded({
    required GameState current,
    required String? winnerId,
    required String? winningAnswer,
    required String? winningAnswerImage,
    required int? points,
    required List<String> validAnswers,
    required List<PlayerAnswer> validAnswerDetails,
    required Map<String, int> scores,
  }) {
    final isWinner = winnerId == current.self?.id;
    final isTimeout = winnerId == null;
    _log('Round ended: ${isTimeout ? "timeout" : isWinner ? "WON" : "LOST"}');

    final result = RoundResult(
      winnerId: winnerId,
      correctAnswer: winningAnswer ?? '',
      correctAnswerImageUrl: winningAnswerImage,
      validAnswers: validAnswers,
      validAnswerDetails: validAnswerDetails,
      pointsEarned: points ?? 0,
      isTimeout: isTimeout,
    );

    // Update scores for self and opponent
    final selfId = current.self?.id;
    final opponentId = current.opponent?.id;
    final selfScore = selfId != null ? scores[selfId] : null;
    final opponentScore = opponentId != null ? scores[opponentId] : null;

    // Update allPlayers list with new scores (for multiplayer leaderboard)
    final updatedAllPlayers = current.allPlayers.map((player) {
      final newScore = scores[player.id];
      if (newScore != null) {
        return player.copyWith(score: newScore);
      }
      return player;
    }).toList();

    return current.copyWith(
      phase: GamePhase.results,
      roundResult: result,
      self: selfScore != null
          ? current.self?.copyWith(score: selfScore)
          : current.self,
      opponent: opponentScore != null
          ? current.opponent?.copyWith(score: opponentScore)
          : current.opponent,
      allPlayers: updatedAllPlayers,
      clearDeadline: true,
    );
  }

  // ============================================================================
  // NEW ROUND
  // ============================================================================

  GameState onPlayAgain(GameState current) {
    _log('Requesting new round...');
    // Don't change state here - wait for server confirmation via onNewRoundFromServer
    return current;
  }

  GameState onNewRoundFromServer(GameState current) {
    _log('New round confirmed by server (${current.roundNumber + 1})');

    return current.copyWith(
      phase: GamePhase.clubSelection,
      roundNumber: current.roundNumber + 1,
      self: current.self?.copyWith(hasSubmittedClub: false, selectedClub: null),
      opponent: current.opponent?.copyWith(hasSubmittedClub: false, selectedClub: null),
      clearMyClub: true,
      clearOpponentClub: true,
      clearRoundResult: true,
      clearDeadline: true,
      clearErrorMessage: true,
    );
  }

  // ============================================================================
  // SETTINGS
  // ============================================================================

  GameState onSportChanged(GameState current, SportType sport) {
    _log('Sport changed: ${sport.displayName}');
    return current.copyWith(sport: sport);
  }

  // ============================================================================
  // ERROR HANDLING
  // ============================================================================

  GameState onError(GameState current, String message) {
    _log('Error: $message');
    return current.copyWith(errorMessage: message);
  }

  // ============================================================================
  // STATE SYNC (RECONNECTION)
  // ============================================================================

  GameState onStateSync({
    required GameState current,
    required int version,
    required String roomCode,
    required SportType sport,
    required GameMode mode,
    required int maxPlayers,
    required String hostId,
    required String phase,
    required String? myClub,
    required String? opponentClub,
    required DateTime? deadline,
    required int validAnswerCount,
    required Player selfPlayer,
    required Player? opponent,
    required List<Player> allPlayers,
    int poolSize = 0,
    List<String> selectedClubs = const [],
    int clubsPerRound = 2,
  }) {
    _log('State sync received: version=$version, phase=$phase, room=$roomCode, mode=${mode.displayName}');

    final gamePhase = GamePhase.fromBackendString(phase);

    return GameState(
      stateVersion: version,
      connectionStatus: ConnectionStatus.connected,
      phase: gamePhase,
      roomCode: roomCode,
      sport: sport,
      mode: mode,
      maxPlayers: maxPlayers,
      hostId: hostId,
      self: selfPlayer,
      opponent: opponent,
      allPlayers: allPlayers,
      roundNumber: current.roundNumber,  // Preserve round number
      myClub: myClub,
      opponentClub: opponentClub,
      selectedClubs: selectedClubs,
      poolSize: poolSize,
      clubsPerRound: clubsPerRound,
      deadline: deadline,
      validAnswerCount: validAnswerCount,
      isCreator: current.isCreator,  // Preserve creator status
      isReconnecting: false,
    );
  }

  // ============================================================================
  // HELPERS
  // ============================================================================

  GameState _resetToHome(GameState current) {
    _log('Resetting to home');
    return GameState.initial.copyWith(
      connectionStatus: current.connectionStatus,
    );
  }

  void _log(String message) {
    debugPrint('[GameOrchestrator] $message');
  }
}
