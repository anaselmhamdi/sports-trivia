import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/game_state.dart';
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

    // Navigate based on phase changes
    ref.listen<GameState>(gameStateProvider, (previous, next) {
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
              child: ResultReveal(
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

                  // Play again button
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

  const _PlayAgainButton({required this.onPressed});

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
        label: const Text('PLAY AGAIN'),
      ),
    );
  }
}
