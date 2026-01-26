import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../models/game_state.dart';
import '../providers/game_provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../widgets/room_code_display.dart';

/// Lobby screen while waiting for opponent
class LobbyScreen extends ConsumerStatefulWidget {
  const LobbyScreen({super.key});

  @override
  ConsumerState<LobbyScreen> createState() => _LobbyScreenState();
}

class _LobbyScreenState extends ConsumerState<LobbyScreen> {
  void _leaveRoom() {
    ref.read(gameStateProvider.notifier).leaveRoom();
  }

  @override
  Widget build(BuildContext context) {
    final gameState = ref.watch(gameStateProvider);
    final isWaiting = gameState.opponent == null;

    // Listen for phase changes and navigate accordingly
    ref.listen<GameState>(gameStateProvider, (previous, next) {
      if (next.phase == GamePhase.clubSelection || next.phase == GamePhase.guessing) {
        context.goNamed('game');
      } else if (next.phase == GamePhase.home) {
        context.goNamed('home');
      } else if (next.phase == GamePhase.results) {
        context.goNamed('result');
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppTheme.spaceLg),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Sport badge
                  _SportBadge(sport: gameState.sport),

                  const SizedBox(height: AppTheme.space2xl),

                  // Room code
                  if (gameState.roomCode != null)
                    RoomCodeDisplay(
                      roomCode: gameState.roomCode!,
                      animate: true,
                    ),

                  const SizedBox(height: AppTheme.space2xl),

                  // Status
                  if (isWaiting)
                    _WaitingStatus()
                  else
                    _OpponentJoinedStatus(
                      opponentName: gameState.opponent?.name ?? 'Opponent',
                    ),

                  const SizedBox(height: AppTheme.space2xl),

                  // Players
                  _PlayersDisplay(
                    selfName: gameState.self?.name ?? 'You',
                    opponentName: gameState.opponent?.name,
                    isWaiting: isWaiting,
                  ),

                  const Spacer(),

                  // Leave button
                  TextButton.icon(
                    onPressed: _leaveRoom,
                    icon: const Icon(Icons.exit_to_app),
                    label: const Text('Leave Room'),
                  ),

                  const SizedBox(height: AppTheme.spaceLg),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SportBadge extends StatelessWidget {
  final SportType sport;

  const _SportBadge({required this.sport});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceMd,
        vertical: AppTheme.spaceSm,
      ),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            sport == SportType.nba ? Icons.sports_basketball : Icons.sports_soccer,
            color: AppColors.primary,
            size: 20,
          ),
          const SizedBox(width: AppTheme.spaceSm),
          Text(
            sport.displayName,
            style: AppTheme.captionStyle.copyWith(
              color: AppColors.primary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    ).animate().fadeIn();
  }
}

class _WaitingStatus extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const _AnimatedWaitingIcon(),
        const SizedBox(height: AppTheme.spaceMd),
        Text(
          'Waiting for opponent',
          style: AppTheme.h3Style,
        ),
        const SizedBox(height: AppTheme.spaceSm),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'Share the room code to invite',
              style: AppTheme.captionStyle,
            ),
            const SizedBox(width: AppTheme.spaceXs),
            const _AnimatedDots(),
          ],
        ),
      ],
    ).animate().fadeIn(delay: const Duration(milliseconds: 300));
  }
}

class _AnimatedWaitingIcon extends StatelessWidget {
  const _AnimatedWaitingIcon();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceLg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.gray700),
      ),
      child: const Icon(
        Icons.hourglass_empty,
        size: 48,
        color: AppColors.primary,
      ),
    )
        .animate(onPlay: (c) => c.repeat())
        .rotate(
          begin: 0,
          end: 0.5,
          duration: const Duration(seconds: 2),
          curve: Curves.easeInOut,
        )
        .then()
        .rotate(
          begin: 0.5,
          end: 1,
          duration: const Duration(seconds: 2),
          curve: Curves.easeInOut,
        );
  }
}

class _AnimatedDots extends StatelessWidget {
  const _AnimatedDots();

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 1),
          child: Text(
            '.',
            style: AppTheme.captionStyle.copyWith(
              fontWeight: FontWeight.bold,
            ),
          )
              .animate(onPlay: (c) => c.repeat())
              .fadeIn(delay: Duration(milliseconds: index * 300))
              .then(delay: const Duration(milliseconds: 600))
              .fadeOut(),
        );
      }),
    );
  }
}

class _OpponentJoinedStatus extends StatelessWidget {
  final String opponentName;

  const _OpponentJoinedStatus({required this.opponentName});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(AppTheme.spaceLg),
          decoration: BoxDecoration(
            color: AppColors.success.withValues(alpha: 0.1),
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.success),
          ),
          child: const Icon(
            Icons.check,
            size: 48,
            color: AppColors.success,
          ),
        )
            .animate()
            .fadeIn()
            .scale(
              begin: const Offset(0.5, 0.5),
              end: const Offset(1, 1),
              curve: Curves.elasticOut,
            ),
        const SizedBox(height: AppTheme.spaceMd),
        Text(
          '$opponentName joined!',
          style: AppTheme.h3Style.copyWith(
            color: AppColors.success,
          ),
        ).animate().fadeIn(delay: const Duration(milliseconds: 200)),
        const SizedBox(height: AppTheme.spaceSm),
        Text(
          'Starting game...',
          style: AppTheme.captionStyle,
        ).animate().fadeIn(delay: const Duration(milliseconds: 400)),
      ],
    );
  }
}

class _PlayersDisplay extends StatelessWidget {
  final String selfName;
  final String? opponentName;
  final bool isWaiting;

  const _PlayersDisplay({
    required this.selfName,
    required this.opponentName,
    required this.isWaiting,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Row(
        children: [
          Expanded(
            child: _PlayerSlot(
              name: selfName,
              label: 'YOU',
              isReady: true,
            ),
          ),
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
              'VS',
              style: AppTheme.captionStyle.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          Expanded(
            child: _PlayerSlot(
              name: opponentName,
              label: 'OPPONENT',
              isReady: opponentName != null,
              isWaiting: isWaiting,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(delay: const Duration(milliseconds: 500));
  }
}

class _PlayerSlot extends StatelessWidget {
  final String? name;
  final String label;
  final bool isReady;
  final bool isWaiting;

  const _PlayerSlot({
    required this.name,
    required this.label,
    required this.isReady,
    this.isWaiting = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: isReady
                ? AppColors.primary.withValues(alpha: 0.1)
                : AppColors.gray700.withValues(alpha: 0.3),
            shape: BoxShape.circle,
            border: Border.all(
              color: isReady ? AppColors.primary : AppColors.gray700,
            ),
          ),
          child: Icon(
            isWaiting ? Icons.hourglass_empty : Icons.person,
            color: isReady ? AppColors.primary : AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: AppTheme.spaceSm),
        Text(
          label,
          style: AppTheme.captionStyle.copyWith(
            letterSpacing: 1,
            fontSize: 10,
          ),
        ),
        const SizedBox(height: AppTheme.spaceXs),
        Text(
          name ?? '---',
          style: AppTheme.bodyStyle.copyWith(
            fontWeight: FontWeight.w600,
            color: isReady ? AppColors.textPrimary : AppColors.textSecondary,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }
}
