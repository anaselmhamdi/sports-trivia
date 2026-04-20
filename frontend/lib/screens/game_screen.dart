import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/game_state.dart';
import '../models/player.dart';
import '../providers/game_provider.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../utils/image_helpers.dart';
import '../widgets/animated_timer.dart';
import '../widgets/club_input.dart';
import '../widgets/grid_board.dart';
import '../widgets/guess_input.dart';
import '../widgets/pulse_container.dart';
import '../widgets/room_code_display.dart';
import '../widgets/score_display.dart';

/// Main game screen handling club selection and guessing phases
class GameScreen extends ConsumerStatefulWidget {
  const GameScreen({super.key});

  @override
  ConsumerState<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends ConsumerState<GameScreen> {
  @override
  Widget build(BuildContext context) {
    final gameState = ref.watch(gameStateProvider);

    // Navigate based on phase changes and show errors
    ref.listen<GameState>(gameStateProvider, (previous, next) {
      // Show errors (club submission failures, guess errors, etc.)
      if (next.errorMessage != null && next.errorMessage != previous?.errorMessage) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.errorMessage!),
            backgroundColor: AppColors.error,
            duration: const Duration(seconds: 3),
          ),
        );
        ref.read(gameStateProvider.notifier).clearError();
      }

      // Notify user if they became the new host
      if (previous != null &&
          next.hostId != previous.hostId &&
          next.hostId == next.self?.id &&
          previous.hostId != next.self?.id) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('You are now the host!'),
            backgroundColor: AppColors.success,
            duration: const Duration(seconds: 3),
          ),
        );
      }

      // Navigate based on phase
      if (next.phase == GamePhase.results) {
        context.goNamed('result');
      } else if (next.phase == GamePhase.home) {
        context.goNamed('home');
      } else if (next.phase == GamePhase.lobby) {
        context.goNamed('lobby');
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Header
            _GameHeader(
              roomCode: gameState.roomCode,
              roundNumber: gameState.roundNumber,
              self: gameState.self,
              opponent: gameState.opponent,
            ),

            // Main content based on phase (and mode for NBA Grid)
            Expanded(
              child: AnimatedSwitcher(
                duration: AppTheme.normalDuration,
                child: gameState.isNbaGrid
                    ? const GridBoard(key: ValueKey('grid'))
                    : gameState.phase == GamePhase.clubSelection
                        ? _ClubSelectionPhase(
                            key: const ValueKey('club_selection'),
                            gameState: gameState,
                          )
                        : _GuessingPhase(
                            key: const ValueKey('guessing'),
                            gameState: gameState,
                          ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GameHeader extends StatelessWidget {
  final String? roomCode;
  final int roundNumber;
  final Player? self;
  final Player? opponent;

  const _GameHeader({
    required this.roomCode,
    required this.roundNumber,
    required this.self,
    required this.opponent,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(
          bottom: BorderSide(color: AppColors.gray700),
        ),
      ),
      child: Row(
        children: [
          // Room code
          if (roomCode != null) CompactRoomCode(roomCode: roomCode!),

          const Spacer(),

          // Round number
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppTheme.spaceMd,
              vertical: AppTheme.spaceSm,
            ),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(AppTheme.radiusFull),
            ),
            child: Text(
              'ROUND $roundNumber',
              style: AppTheme.captionStyle.copyWith(
                color: AppColors.primary,
                letterSpacing: 2,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),

          const Spacer(),

          // Score
          ScoreDisplay(
            self: self,
            opponent: opponent,
            compact: true,
          ),
        ],
      ),
    );
  }
}

class _ClubSelectionPhase extends ConsumerStatefulWidget {
  final GameState gameState;

  const _ClubSelectionPhase({
    super.key,
    required this.gameState,
  });

  @override
  ConsumerState<_ClubSelectionPhase> createState() => _ClubSelectionPhaseState();
}

class _ClubSelectionPhaseState extends ConsumerState<_ClubSelectionPhase> {
  final _clubController = TextEditingController();
  bool _hasSubmitted = false;
  List<ClubInfo> _clubs = [];
  bool _isLoadingClubs = true;
  String? _selectedClubBadge;
  final ApiService _apiService = ApiService();
  int _selectedClubsPerRound = 2;

  @override
  void initState() {
    super.initState();
    _loadClubs();
  }

  @override
  void didUpdateWidget(_ClubSelectionPhase oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Reset submission state if error occurred (parent shows snackbar)
    if (widget.gameState.errorMessage != null &&
        widget.gameState.errorMessage != oldWidget.gameState.errorMessage) {
      setState(() => _hasSubmitted = false);
    }
  }

  Future<void> _loadClubs() async {
    final sportKey = widget.gameState.sport == SportType.nba ? 'nba' : 'soccer';
    final clubs = await _apiService.getClubs(sportKey);
    if (mounted) {
      setState(() {
        _clubs = clubs;
        _isLoadingClubs = false;
      });
    }
  }

  @override
  void dispose() {
    _clubController.dispose();
    super.dispose();
  }

  void _submitClub(String clubName) {
    if (clubName.isEmpty || _hasSubmitted) return;

    // Find the badge URL for the selected club
    final matchingClub = _clubs.where(
      (club) => club.fullName.toLowerCase() == clubName.toLowerCase() ||
                club.displayName.toLowerCase() == clubName.toLowerCase(),
    ).firstOrNull;

    setState(() {
      _hasSubmitted = true;
      _selectedClubBadge = matchingClub?.badge ?? matchingClub?.logo;
    });
    ref.read(gameStateProvider.notifier).submitClub(clubName);
  }

  void _startRound() {
    ref.read(gameStateProvider.notifier).startRound(clubsPerRound: _selectedClubsPerRound);
  }

  @override
  Widget build(BuildContext context) {
    final selfSubmitted = widget.gameState.self?.hasSubmittedClub ?? false;
    final opponentSubmitted = widget.gameState.opponent?.hasSubmittedClub ?? false;
    final isMultiplayer = widget.gameState.isMultiplayer;

    // For multiplayer, use different UI
    if (isMultiplayer) {
      return _buildMultiplayerClubSelection(selfSubmitted);
    }

    return Padding(
      padding: const EdgeInsets.all(AppTheme.spaceLg),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 500),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Instructions
              Text(
                'PICK A TEAM',
                style: AppTheme.h2Style,
              ).animate().fadeIn(),
              const SizedBox(height: AppTheme.spaceSm),
              Text(
                'Choose a ${widget.gameState.sport.displayName} team for your opponent to guess a player from',
                style: AppTheme.captionStyle,
                textAlign: TextAlign.center,
              ).animate().fadeIn(delay: const Duration(milliseconds: 100)),

              const SizedBox(height: AppTheme.space2xl),

              // Your submission
              ClubSubmissionCard(
                title: 'YOUR TEAM',
                isSubmitted: selfSubmitted || _hasSubmitted,
                submittedClub: _hasSubmitted
                    ? _clubController.text
                    : widget.gameState.self?.selectedClub,
                submittedClubBadge: _selectedClubBadge,
                input: ClubInput(
                  controller: _clubController,
                  hint: _isLoadingClubs ? 'Loading teams...' : 'Enter team name...',
                  enabled: !selfSubmitted && !_hasSubmitted && !_isLoadingClubs,
                  autofocus: true,
                  onSubmitted: _submitClub,
                  clubs: _clubs,
                  sport: widget.gameState.sport == SportType.nba ? 'nba' : 'soccer',
                ),
              ).animate().fadeIn(delay: const Duration(milliseconds: 200)),

              const SizedBox(height: AppTheme.spaceMd),

              // Opponent status
              ClubSubmissionCard(
                title: 'OPPONENT',
                isSubmitted: opponentSubmitted,
                isLoading: !opponentSubmitted,
              ).animate().fadeIn(delay: const Duration(milliseconds: 300)),

              const SizedBox(height: AppTheme.spaceLg),

              // Status message
              if (selfSubmitted && !opponentSubmitted)
                Text(
                  'Waiting for opponent to pick their team...',
                  style: AppTheme.captionStyle,
                )
                    .animate(onPlay: (c) => c.repeat())
                    .fadeIn()
                    .then()
                    .fadeOut(delay: const Duration(seconds: 1)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMultiplayerClubSelection(bool selfSubmitted) {
    final poolSize = widget.gameState.poolSize;
    final canStartRound = widget.gameState.canStartRound;
    final isHost = widget.gameState.isHost;
    final maxClubsPerRound = poolSize.clamp(2, 4);

    return Padding(
      padding: const EdgeInsets.all(AppTheme.spaceLg),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 500),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Instructions
              Text(
                'SUBMIT YOUR TEAM',
                style: AppTheme.h2Style,
              ).animate().fadeIn(),
              const SizedBox(height: AppTheme.spaceSm),
              Text(
                'Add a ${widget.gameState.sport.displayName} team to the pool',
                style: AppTheme.captionStyle,
                textAlign: TextAlign.center,
              ).animate().fadeIn(delay: const Duration(milliseconds: 100)),

              const SizedBox(height: AppTheme.spaceLg),

              // Pool status
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppTheme.spaceLg,
                  vertical: AppTheme.spaceMd,
                ),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(AppTheme.radiusLg),
                  border: Border.all(
                    color: canStartRound
                        ? AppColors.success.withValues(alpha: 0.5)
                        : AppColors.gray700,
                  ),
                ),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.sports,
                          color: canStartRound ? AppColors.success : AppColors.textSecondary,
                          size: 24,
                        ),
                        const SizedBox(width: AppTheme.spaceSm),
                        Text(
                          '$poolSize teams in pool',
                          style: AppTheme.h3Style.copyWith(
                            color: canStartRound ? AppColors.success : AppColors.textPrimary,
                          ),
                        ),
                      ],
                    ),
                    if (!canStartRound) ...[
                      const SizedBox(height: AppTheme.spaceSm),
                      Text(
                        'Need at least 2 teams to start',
                        style: AppTheme.captionStyle,
                      ),
                    ],
                  ],
                ),
              ).animate().fadeIn(delay: const Duration(milliseconds: 150)),

              const SizedBox(height: AppTheme.spaceLg),

              // Your submission
              ClubSubmissionCard(
                title: 'YOUR TEAM',
                isSubmitted: selfSubmitted || _hasSubmitted,
                submittedClub: _hasSubmitted
                    ? _clubController.text
                    : widget.gameState.self?.selectedClub,
                submittedClubBadge: _selectedClubBadge,
                input: ClubInput(
                  controller: _clubController,
                  hint: _isLoadingClubs ? 'Loading teams...' : 'Enter team name...',
                  enabled: !selfSubmitted && !_hasSubmitted && !_isLoadingClubs,
                  autofocus: true,
                  onSubmitted: _submitClub,
                  clubs: _clubs,
                  sport: widget.gameState.sport == SportType.nba ? 'nba' : 'soccer',
                ),
              ).animate().fadeIn(delay: const Duration(milliseconds: 200)),

              const SizedBox(height: AppTheme.spaceLg),

              // Host controls
              if (isHost && canStartRound) ...[
                // Difficulty selector
                Container(
                  padding: const EdgeInsets.all(AppTheme.spaceMd),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(AppTheme.radiusLg),
                    border: Border.all(color: AppColors.gray700),
                  ),
                  child: Column(
                    children: [
                      Text(
                        'DIFFICULTY',
                        style: AppTheme.captionStyle.copyWith(
                          letterSpacing: 1,
                          fontSize: 10,
                        ),
                      ),
                      const SizedBox(height: AppTheme.spaceSm),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          for (int i = 2; i <= maxClubsPerRound; i++)
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 4),
                              child: _DifficultyChip(
                                clubs: i,
                                isSelected: _selectedClubsPerRound == i,
                                onTap: () => setState(() => _selectedClubsPerRound = i),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ).animate().fadeIn(delay: const Duration(milliseconds: 250)),

                const SizedBox(height: AppTheme.spaceMd),

                ElevatedButton(
                  onPressed: _startRound,
                  child: const Text('START ROUND'),
                ).animate().fadeIn(delay: const Duration(milliseconds: 300)),
              ] else if (!isHost && canStartRound) ...[
                Text(
                  'Waiting for host to start round...',
                  style: AppTheme.captionStyle,
                )
                    .animate(onPlay: (c) => c.repeat())
                    .fadeIn()
                    .then()
                    .fadeOut(delay: const Duration(seconds: 1)),
              ],
            ],
          ),
        ),
      ),
    );
  }

}

class _DifficultyChip extends StatelessWidget {
  final int clubs;
  final bool isSelected;
  final VoidCallback onTap;

  const _DifficultyChip({
    required this.clubs,
    required this.isSelected,
    required this.onTap,
  });

  String get _label {
    switch (clubs) {
      case 2:
        return 'Normal';
      case 3:
        return 'Hard';
      case 4:
        return 'Expert';
      default:
        return '$clubs clubs';
    }
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: AppTheme.fastDuration,
        padding: const EdgeInsets.symmetric(
          horizontal: AppTheme.spaceMd,
          vertical: AppTheme.spaceSm,
        ),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary : Colors.transparent,
          borderRadius: BorderRadius.circular(AppTheme.radiusFull),
          border: Border.all(
            color: isSelected ? AppColors.primary : AppColors.gray700,
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              _label,
              style: AppTheme.captionStyle.copyWith(
                color: isSelected ? AppColors.voidBlack : AppColors.textPrimary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
              ),
            ),
            Text(
              '$clubs teams',
              style: TextStyle(
                fontSize: 10,
                color: isSelected
                    ? AppColors.voidBlack.withValues(alpha: 0.7)
                    : AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GuessingPhase extends ConsumerStatefulWidget {
  final GameState gameState;

  const _GuessingPhase({
    super.key,
    required this.gameState,
  });

  @override
  ConsumerState<_GuessingPhase> createState() => _GuessingPhaseState();
}

class _GuessingPhaseState extends ConsumerState<_GuessingPhase> {
  bool _showError = false;
  Timer? _errorTimer;

  @override
  void dispose() {
    _errorTimer?.cancel();
    super.dispose();
  }

  void _submitGuess(String guess) {
    if (guess.isEmpty) return;
    ref.read(gameStateProvider.notifier).submitGuess(guess);
  }

  @override
  void didUpdateWidget(_GuessingPhase oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Show error animation when error message appears
    if (widget.gameState.errorMessage != null &&
        widget.gameState.errorMessage != oldWidget.gameState.errorMessage) {
      setState(() => _showError = true);
      _errorTimer?.cancel();
      _errorTimer = Timer(const Duration(milliseconds: 800), () {
        if (mounted) {
          setState(() => _showError = false);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final remainingTime = ref.watch(remainingTimeProvider);
    final urgency = ref.watch(timerUrgencyProvider);

    return Stack(
      children: [
        // Urgency border overlay
        if (urgency > 0)
          Positioned.fill(
            child: IgnorePointer(
              child: Container(
                decoration: BoxDecoration(
                  border: Border.all(
                    color: urgency > 1
                        ? AppColors.lossRed.withValues(alpha: 0.3)
                        : AppColors.pulseOrange.withValues(alpha: 0.2),
                    width: urgency > 1 ? 4 : 2,
                  ),
                ),
              )
                  .animate(onPlay: (c) => c.repeat(reverse: true))
                  .fadeIn(duration: Duration(milliseconds: urgency > 1 ? 250 : 500))
                  .then()
                  .fadeOut(duration: Duration(milliseconds: urgency > 1 ? 250 : 500)),
            ),
          ),

        // Main content
        Padding(
          padding: const EdgeInsets.all(AppTheme.spaceLg),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 500),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Timer
                  remainingTime.when(
                    data: (time) => AnimatedTimer(
                      remainingSeconds: time,
                      totalSeconds: 60,
                      size: 180,
                    ),
                    loading: () => const AnimatedTimer(
                      remainingSeconds: 60,
                      totalSeconds: 60,
                      size: 180,
                    ),
                    error: (_, __) => const AnimatedTimer(
                      remainingSeconds: 0,
                      totalSeconds: 60,
                      size: 180,
                    ),
                  ),

                  const SizedBox(height: AppTheme.spaceLg),

                  // Club matchup display - use multi-club view for 3+ clubs
                  if (widget.gameState.selectedClubs.length > 2)
                    _MultiClubMatchup(
                      clubs: widget.gameState.selectedClubs,
                      clubLogos: widget.gameState.selectedClubLogos,
                      sport: widget.gameState.sport,
                    )
                  else
                    _ClubMatchup(
                      myClub: widget.gameState.myClub ?? '???',
                      opponentClub: widget.gameState.opponentClub ?? '???',
                      myClubLogo: widget.gameState.myClubLogo,
                      opponentClubLogo: widget.gameState.opponentClubLogo,
                      sport: widget.gameState.sport,
                    ),

                  const SizedBox(height: AppTheme.spaceMd),

                  // Valid answer count hint
                  if (widget.gameState.validAnswerCount > 0)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppTheme.spaceMd,
                        vertical: AppTheme.spaceSm,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
                        border: Border.all(color: AppColors.gray700),
                      ),
                      child: Text(
                        '${widget.gameState.validAnswerCount} possible answers',
                        style: AppTheme.captionStyle,
                      ),
                    ).animate().fadeIn(),

                  const SizedBox(height: AppTheme.spaceLg),

                  // Guess input
                  UrgencyBorder(
                    urgencyLevel: urgency,
                    borderRadius: BorderRadius.circular(AppTheme.radiusLg),
                    child: Padding(
                      padding: const EdgeInsets.all(AppTheme.spaceMd),
                      child: GuessInput(
                        onSubmitted: _submitGuess,
                        showError: _showError,
                        hint: widget.gameState.selectedClubs.length > 2
                            ? 'Name a player who played for ALL ${widget.gameState.selectedClubs.length} teams...'
                            : 'Name a player who played for both teams...',
                      ),
                    ),
                  ),

                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ClubMatchup extends StatelessWidget {
  final String myClub;
  final String opponentClub;
  final String? myClubLogo;
  final String? opponentClubLogo;
  final SportType sport;

  const _ClubMatchup({
    required this.myClub,
    required this.opponentClub,
    this.myClubLogo,
    this.opponentClubLogo,
    required this.sport,
  });

  Widget _buildClubBadge(String name, String? logoUrl, Color accentColor, bool isLeft) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Club crest with dramatic glow
        Container(
          width: 80,
          height: 80,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                accentColor.withValues(alpha: 0.15),
                accentColor.withValues(alpha: 0.05),
                Colors.transparent,
              ],
              stops: const [0.0, 0.6, 1.0],
            ),
            boxShadow: [
              BoxShadow(
                color: accentColor.withValues(alpha: 0.3),
                blurRadius: 24,
                spreadRadius: -4,
              ),
            ],
          ),
          child: Container(
            margin: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.surfaceLight,
              border: Border.all(
                color: accentColor.withValues(alpha: 0.4),
                width: 2,
              ),
            ),
            child: ClipOval(
              child: logoUrl != null
                  ? Image.network(
                      getProxiedImageUrl(logoUrl) ?? '',
                      width: 64,
                      height: 64,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => _buildFallbackIcon(accentColor),
                    )
                  : _buildFallbackIcon(accentColor),
            ),
          ),
        ),
        const SizedBox(height: AppTheme.spaceMd),
        // Club name with accent underline
        Column(
          children: [
            Text(
              name.toUpperCase(),
              style: AppTheme.h2Style.copyWith(
                color: AppColors.textPrimary,
                fontSize: 14,
                letterSpacing: 1.5,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 6),
            Container(
              width: 32,
              height: 2,
              decoration: BoxDecoration(
                color: accentColor,
                borderRadius: BorderRadius.circular(1),
                boxShadow: [
                  BoxShadow(
                    color: accentColor.withValues(alpha: 0.6),
                    blurRadius: 6,
                  ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildFallbackIcon(Color color) {
    return Center(
      child: Icon(
        sport == SportType.nba ? Icons.sports_basketball : Icons.sports_soccer,
        color: color,
        size: 32,
      ),
    );
  }

  Widget _buildCrossSeparator() {
    return SizedBox(
      width: 48,
      child: Center(
        child: Text(
          'X',
          style: AppTheme.h2Style.copyWith(
            fontSize: 28,
            color: AppColors.gray500,
            fontWeight: FontWeight.w400,
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppTheme.spaceMd,
            vertical: AppTheme.spaceLg,
          ),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(AppTheme.radiusXl),
            border: Border.all(
              color: AppColors.gray700.withValues(alpha: 0.5),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.3),
                blurRadius: 20,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: _buildClubBadge(myClub, myClubLogo, AppColors.electricCyan, true),
              ),
              _buildCrossSeparator(),
              Expanded(
                child: _buildClubBadge(opponentClub, opponentClubLogo, AppColors.pulseOrange, false),
              ),
            ],
          ),
        ),
        const SizedBox(height: AppTheme.spaceMd),
        Text(
          'Name a player who played for both!',
          style: AppTheme.captionStyle.copyWith(
            color: AppColors.gray400,
            letterSpacing: 0.5,
          ),
        ),
      ],
    )
        .animate()
        .fadeIn(duration: AppTheme.normalDuration)
        .scale(
          begin: const Offset(0.95, 0.95),
          end: const Offset(1, 1),
          curve: Curves.easeOutCubic,
          duration: AppTheme.slowDuration,
        );
  }
}

/// Multi-club matchup display for 3-4 clubs in multiplayer mode
class _MultiClubMatchup extends StatelessWidget {
  final List<String> clubs;
  final List<String?> clubLogos;
  final SportType sport;

  const _MultiClubMatchup({
    required this.clubs,
    required this.clubLogos,
    required this.sport,
  });

  static const _colors = [
    AppColors.electricCyan,
    AppColors.pulseOrange,
    AppColors.success,
    AppColors.primary,
  ];

  Widget _buildClubBadge(int index) {
    final name = index < clubs.length ? clubs[index] : '???';
    final logoUrl = index < clubLogos.length ? clubLogos[index] : null;
    final color = _colors[index % _colors.length];

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(
              colors: [
                color.withValues(alpha: 0.15),
                color.withValues(alpha: 0.05),
                Colors.transparent,
              ],
              stops: const [0.0, 0.6, 1.0],
            ),
            boxShadow: [
              BoxShadow(
                color: color.withValues(alpha: 0.3),
                blurRadius: 16,
                spreadRadius: -4,
              ),
            ],
          ),
          child: Container(
            margin: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: AppColors.surfaceLight,
              border: Border.all(
                color: color.withValues(alpha: 0.4),
                width: 2,
              ),
            ),
            child: ClipOval(
              child: logoUrl != null
                  ? Image.network(
                      getProxiedImageUrl(logoUrl) ?? '',
                      width: 52,
                      height: 52,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => _buildFallbackIcon(color),
                    )
                  : _buildFallbackIcon(color),
            ),
          ),
        ),
        const SizedBox(height: AppTheme.spaceSm),
        SizedBox(
          width: 80,
          child: Text(
            name.toUpperCase(),
            style: AppTheme.captionStyle.copyWith(
              color: AppColors.textPrimary,
              fontSize: 10,
              letterSpacing: 1,
              fontWeight: FontWeight.w600,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }

  Widget _buildFallbackIcon(Color color) {
    return Center(
      child: Icon(
        sport == SportType.nba ? Icons.sports_basketball : Icons.sports_soccer,
        color: color,
        size: 24,
      ),
    );
  }

  Widget _buildPlusSeparator() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Text(
        '+',
        style: AppTheme.h3Style.copyWith(
          color: AppColors.gray500,
          fontSize: 20,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppTheme.spaceMd,
            vertical: AppTheme.spaceLg,
          ),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(AppTheme.radiusXl),
            border: Border.all(
              color: AppColors.gray700.withValues(alpha: 0.5),
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.3),
                blurRadius: 20,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Wrap(
            alignment: WrapAlignment.center,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            runSpacing: 12,
            children: [
              for (int i = 0; i < clubs.length; i++) ...[
                if (i > 0) _buildPlusSeparator(),
                _buildClubBadge(i),
              ],
            ],
          ),
        ),
        const SizedBox(height: AppTheme.spaceMd),
        Text(
          'Name a player who played for ALL ${clubs.length}!',
          style: AppTheme.captionStyle.copyWith(
            color: AppColors.gray400,
            letterSpacing: 0.5,
          ),
        ),
      ],
    )
        .animate()
        .fadeIn(duration: AppTheme.normalDuration)
        .scale(
          begin: const Offset(0.95, 0.95),
          end: const Offset(1, 1),
          curve: Curves.easeOutCubic,
          duration: AppTheme.slowDuration,
        );
  }
}
