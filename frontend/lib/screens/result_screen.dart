import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/game_state.dart';
import '../models/player.dart';
import '../providers/game_provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../widgets/result_reveal.dart';

/// Result screen showing round outcome
class ResultScreen extends ConsumerStatefulWidget {
  const ResultScreen({super.key});

  @override
  ConsumerState<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends ConsumerState<ResultScreen> {
  void _playAgain() {
    ref.read(gameStateProvider.notifier).playAgain();
  }

  void _leaveRoom() {
    ref.read(gameStateProvider.notifier).leaveRoom();
  }

  @override
  Widget build(BuildContext context) {
    final gameState = ref.watch(gameStateProvider);
    final result = gameState.roundResult;

    // Navigate based on phase changes and show errors
    ref.listen<GameState>(gameStateProvider, (previous, next) {
      // Show errors (e.g., selection failed when starting next round)
      if (next.errorMessage != null && next.errorMessage != previous?.errorMessage) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(next.errorMessage!),
            backgroundColor: AppColors.error,
            duration: const Duration(seconds: 4),
          ),
        );
        ref.read(gameStateProvider.notifier).clearError();
      }

      // Navigate based on phase
      if (next.phase == GamePhase.clubSelection || next.phase == GamePhase.guessing) {
        context.goNamed('game');
      } else if (next.phase == GamePhase.home) {
        context.goNamed('home');
      } else if (next.phase == GamePhase.lobby) {
        context.goNamed('lobby');
      }
    });

    if (result == null) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(color: AppColors.primary),
        ),
      );
    }

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.all(AppTheme.spaceMd),
              decoration: const BoxDecoration(
                color: AppColors.surface,
                border: Border(
                  bottom: BorderSide(color: AppColors.gray700),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'ROUND ${gameState.roundNumber} RESULTS',
                    style: AppTheme.h3Style.copyWith(
                      letterSpacing: 2,
                    ),
                  ),
                ],
              ),
            ),

            // Result reveal
            Expanded(
              child: gameState.isMultiplayer
                  ? _MultiplayerResults(
                      result: result,
                      players: gameState.allPlayers,
                      selfId: gameState.self?.id,
                      sport: gameState.sport,
                    )
                  : ResultReveal(
                      result: result,
                      selfId: gameState.self?.id,
                      selfScore: gameState.self?.score ?? 0,
                      opponentScore: gameState.opponent?.score ?? 0,
                      sport: gameState.sport,
                    ),
            ),

            // Action buttons
            Container(
              padding: const EdgeInsets.all(AppTheme.spaceLg),
              decoration: const BoxDecoration(
                color: AppColors.surface,
                border: Border(
                  top: BorderSide(color: AppColors.gray700),
                ),
              ),
              child: Row(
                children: [
                  // Leave button
                  TextButton(
                    onPressed: _leaveRoom,
                    child: const Text('Leave'),
                  ),

                  const Spacer(),

                  // Play again button (host only in multiplayer)
                  if (gameState.isMultiplayer)
                    if (gameState.isHost)
                      _PlayAgainButton(onPressed: _playAgain, label: 'NEXT ROUND')
                    else
                      Text(
                        'Waiting for host...',
                        style: AppTheme.captionStyle,
                      ).animate(onPlay: (c) => c.repeat())
                          .fadeIn()
                          .then()
                          .fadeOut(delay: const Duration(seconds: 1))
                  else
                    _PlayAgainButton(onPressed: _playAgain),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PlayAgainButton extends StatefulWidget {
  final VoidCallback onPressed;
  final String label;

  const _PlayAgainButton({required this.onPressed, this.label = 'PLAY AGAIN'});

  @override
  State<_PlayAgainButton> createState() => _PlayAgainButtonState();
}

class _PlayAgainButtonState extends State<_PlayAgainButton>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  bool _startPulse = false;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );

    // Start pulsing after 2 seconds
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() => _startPulse = true);
        _pulseController.repeat(reverse: true);
      }
    });
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        return Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppTheme.radiusMd),
            boxShadow: _startPulse
                ? [
                    BoxShadow(
                      color: AppColors.success
                          .withValues(alpha: 0.3 + (_pulseController.value * 0.2)),
                      blurRadius: 10 + (_pulseController.value * 10),
                      spreadRadius: _pulseController.value * 2,
                    ),
                  ]
                : null,
          ),
          child: child,
        );
      },
      child: ElevatedButton.icon(
        onPressed: widget.onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.success,
          foregroundColor: AppColors.voidBlack,
          padding: const EdgeInsets.symmetric(
            horizontal: AppTheme.spaceLg,
            vertical: AppTheme.spaceMd,
          ),
        ),
        icon: const Icon(Icons.replay),
        label: Text(widget.label),
      ),
    );
  }
}

/// Multiplayer results view with leaderboard
class _MultiplayerResults extends StatelessWidget {
  final RoundResult result;
  final List<Player> players;
  final String? selfId;
  final SportType sport;

  const _MultiplayerResults({
    required this.result,
    required this.players,
    this.selfId,
    required this.sport,
  });

  @override
  Widget build(BuildContext context) {
    final isWinner = result.winnerId == selfId;
    final isTimeout = result.isTimeout;

    // Sort players by score descending
    final sortedPlayers = List<Player>.from(players)
      ..sort((a, b) => b.score.compareTo(a.score));

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppTheme.spaceLg),
      child: Column(
        children: [
          // Result banner
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppTheme.spaceLg),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: isTimeout
                    ? [AppColors.gray700, AppColors.gray800]
                    : isWinner
                        ? [AppColors.success.withValues(alpha: 0.2), AppColors.success.withValues(alpha: 0.1)]
                        : [AppColors.error.withValues(alpha: 0.2), AppColors.error.withValues(alpha: 0.1)],
              ),
              borderRadius: BorderRadius.circular(AppTheme.radiusLg),
              border: Border.all(
                color: isTimeout
                    ? AppColors.gray600
                    : isWinner
                        ? AppColors.success.withValues(alpha: 0.5)
                        : AppColors.error.withValues(alpha: 0.5),
              ),
            ),
            child: Column(
              children: [
                Icon(
                  isTimeout
                      ? Icons.timer_off
                      : isWinner
                          ? Icons.emoji_events
                          : Icons.close,
                  size: 48,
                  color: isTimeout
                      ? AppColors.textSecondary
                      : isWinner
                          ? AppColors.success
                          : AppColors.error,
                ),
                const SizedBox(height: AppTheme.spaceMd),
                Text(
                  isTimeout
                      ? "TIME'S UP!"
                      : isWinner
                          ? 'YOU WIN!'
                          : 'YOU LOSE',
                  style: AppTheme.h2Style.copyWith(
                    color: isTimeout
                        ? AppColors.textSecondary
                        : isWinner
                            ? AppColors.success
                            : AppColors.error,
                  ),
                ),
                if (result.correctAnswer.isNotEmpty) ...[
                  const SizedBox(height: AppTheme.spaceSm),
                  Text(
                    'Answer: ${result.correctAnswer}',
                    style: AppTheme.bodyStyle.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ).animate().fadeIn().scale(
                begin: const Offset(0.9, 0.9),
                curve: Curves.elasticOut,
              ),

          const SizedBox(height: AppTheme.space2xl),

          // Leaderboard header
          Row(
            children: [
              const Icon(Icons.leaderboard, color: AppColors.primary, size: 20),
              const SizedBox(width: AppTheme.spaceSm),
              Text(
                'LEADERBOARD',
                style: AppTheme.h3Style.copyWith(
                  letterSpacing: 2,
                ),
              ),
            ],
          ).animate().fadeIn(delay: const Duration(milliseconds: 200)),

          const SizedBox(height: AppTheme.spaceMd),

          // Player rankings
          ...sortedPlayers.asMap().entries.map((entry) {
            final index = entry.key;
            final player = entry.value;
            final isMe = player.id == selfId;
            final isRoundWinner = player.id == result.winnerId;

            return Container(
              margin: const EdgeInsets.only(bottom: AppTheme.spaceSm),
              padding: const EdgeInsets.all(AppTheme.spaceMd),
              decoration: BoxDecoration(
                color: isMe
                    ? AppColors.primary.withValues(alpha: 0.1)
                    : AppColors.surface,
                borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                border: Border.all(
                  color: isMe
                      ? AppColors.primary.withValues(alpha: 0.5)
                      : isRoundWinner
                          ? AppColors.success.withValues(alpha: 0.5)
                          : AppColors.gray700,
                ),
              ),
              child: Row(
                children: [
                  // Rank
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: index == 0
                          ? AppColors.gold.withValues(alpha: 0.2)
                          : index == 1
                              ? AppColors.silver.withValues(alpha: 0.2)
                              : index == 2
                                  ? AppColors.bronze.withValues(alpha: 0.2)
                                  : AppColors.gray700.withValues(alpha: 0.3),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        '${index + 1}',
                        style: AppTheme.bodyStyle.copyWith(
                          fontWeight: FontWeight.bold,
                          color: index == 0
                              ? AppColors.gold
                              : index == 1
                                  ? AppColors.silver
                                  : index == 2
                                      ? AppColors.bronze
                                      : AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppTheme.spaceMd),

                  // Name
                  Expanded(
                    child: Row(
                      children: [
                        Text(
                          player.name,
                          style: AppTheme.bodyStyle.copyWith(
                            fontWeight: isMe ? FontWeight.w600 : FontWeight.normal,
                          ),
                        ),
                        if (isMe) ...[
                          const SizedBox(width: AppTheme.spaceSm),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.primary.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(AppTheme.radiusFull),
                            ),
                            child: Text(
                              'YOU',
                              style: TextStyle(
                                fontSize: 10,
                                color: AppColors.primary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                        if (isRoundWinner) ...[
                          const SizedBox(width: AppTheme.spaceSm),
                          const Icon(
                            Icons.star,
                            size: 16,
                            color: AppColors.success,
                          ),
                        ],
                      ],
                    ),
                  ),

                  // Score
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppTheme.spaceMd,
                      vertical: AppTheme.spaceSm,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(AppTheme.radiusFull),
                    ),
                    child: Text(
                      '${player.score}',
                      style: AppTheme.h3Style.copyWith(
                        fontSize: 16,
                        color: AppColors.primary,
                      ),
                    ),
                  ),
                ],
              ),
            ).animate().fadeIn(delay: Duration(milliseconds: 300 + (index * 100)));
          }),
        ],
      ),
    );
  }
}
