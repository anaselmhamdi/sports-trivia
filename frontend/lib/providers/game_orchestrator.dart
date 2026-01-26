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
  }) {
    _log('Room created: $roomCode (${sport.displayName})');

    return current.copyWith(
      phase: GamePhase.lobby,
      roomCode: roomCode,
      sport: sport,
      self: self,
      isCreator: true,
      roundNumber: 1,
      clearOpponent: true,
      clearRoundResult: true,
    );
  }

  GameState onRoomJoined({
    required GameState current,
    required String roomCode,
    required Player self,
    required Player? opponent,
    required SportType sport,
    required String phase,
  }) {
    _log('Room joined: $roomCode, opponent: ${opponent?.name ?? "none"}, phase: $phase');

    // Use the phase from the backend - it's the source of truth
    final gamePhase = GamePhase.fromBackendString(phase);

    return current.copyWith(
      phase: gamePhase,
      roomCode: roomCode,
      sport: sport,
      self: self,
      opponent: opponent,
      isCreator: false,
      roundNumber: 1,
    );
  }

  GameState onOpponentJoined(GameState current, Player opponent, String phase) {
    _log('Opponent joined: ${opponent.name}, phase: $phase');

    // Use the phase from the backend - it's the source of truth
    final gamePhase = GamePhase.fromBackendString(phase);

    return current.copyWith(
      phase: gamePhase,
      opponent: opponent,
    );
  }

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
    required DateTime deadline,
    required int validAnswerCount,
  }) {
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

    // Update scores
    final selfId = current.self?.id;
    final opponentId = current.opponent?.id;
    final selfScore = selfId != null ? scores[selfId] : null;
    final opponentScore = opponentId != null ? scores[opponentId] : null;

    return current.copyWith(
      phase: GamePhase.results,
      roundResult: result,
      self: selfScore != null
          ? current.self?.copyWith(score: selfScore)
          : current.self,
      opponent: opponentScore != null
          ? current.opponent?.copyWith(score: opponentScore)
          : current.opponent,
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
    required String phase,
    required String? myClub,
    required String? opponentClub,
    required DateTime? deadline,
    required int validAnswerCount,
    required Player selfPlayer,
    required Player? opponent,
  }) {
    _log('State sync received: version=$version, phase=$phase, room=$roomCode');

    final gamePhase = GamePhase.fromBackendString(phase);

    return GameState(
      stateVersion: version,
      connectionStatus: ConnectionStatus.connected,
      phase: gamePhase,
      roomCode: roomCode,
      sport: sport,
      self: selfPlayer,
      opponent: opponent,
      roundNumber: current.roundNumber,  // Preserve round number
      myClub: myClub,
      opponentClub: opponentClub,
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
