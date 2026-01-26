import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import '../models/player.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Displays scores for both players with animations
class ScoreDisplay extends StatelessWidget {
  final Player? self;
  final Player? opponent;
  final bool compact;

  const ScoreDisplay({
    super.key,
    required this.self,
    required this.opponent,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return _CompactScoreDisplay(self: self, opponent: opponent);
    }

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Expanded(
          child: _PlayerScoreCard(
            player: self,
            label: 'YOU',
            isHighlighted: (self?.score ?? 0) > (opponent?.score ?? 0),
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: AppTheme.spaceMd),
          child: _VsDivider(),
        ),
        Expanded(
          child: _PlayerScoreCard(
            player: opponent,
            label: 'OPPONENT',
            isHighlighted: (opponent?.score ?? 0) > (self?.score ?? 0),
          ),
        ),
      ],
    );
  }
}

class _PlayerScoreCard extends StatelessWidget {
  final Player? player;
  final String label;
  final bool isHighlighted;

  const _PlayerScoreCard({
    required this.player,
    required this.label,
    required this.isHighlighted,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(
          color: isHighlighted ? AppColors.primary : AppColors.gray700,
          width: isHighlighted ? 2 : 1,
        ),
        boxShadow: isHighlighted ? AppTheme.glowShadow(AppColors.primary) : null,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: AppTheme.captionStyle.copyWith(
              letterSpacing: 2,
              color: isHighlighted ? AppColors.primary : AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: AppTheme.spaceSm),
          Text(
            player?.name ?? '---',
            style: AppTheme.bodyStyle.copyWith(
              fontWeight: FontWeight.w600,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AppTheme.spaceSm),
          AnimatedScoreNumber(
            score: player?.score ?? 0,
            color: isHighlighted ? AppColors.primary : AppColors.textPrimary,
          ),
        ],
      ),
    );
  }
}

class _CompactScoreDisplay extends StatelessWidget {
  final Player? self;
  final Player? opponent;

  const _CompactScoreDisplay({
    required this.self,
    required this.opponent,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceMd,
        vertical: AppTheme.spaceSm,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${self?.score ?? 0}',
            style: AppTheme.scoreStyle.copyWith(
              fontSize: 20,
              color: (self?.score ?? 0) > (opponent?.score ?? 0)
                  ? AppColors.primary
                  : AppColors.textPrimary,
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppTheme.spaceSm),
            child: Text(
              '-',
              style: AppTheme.bodyStyle.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ),
          Text(
            '${opponent?.score ?? 0}',
            style: AppTheme.scoreStyle.copyWith(
              fontSize: 20,
              color: (opponent?.score ?? 0) > (self?.score ?? 0)
                  ? AppColors.pulseOrange
                  : AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

class _VsDivider extends StatelessWidget {
  const _VsDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceSm),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        shape: BoxShape.circle,
        border: Border.all(color: AppColors.gray700),
      ),
      child: Text(
        'VS',
        style: AppTheme.captionStyle.copyWith(
          fontWeight: FontWeight.bold,
          letterSpacing: 1,
        ),
      ),
    );
  }
}

/// Animated score number with pop effect on change
class AnimatedScoreNumber extends StatelessWidget {
  final int score;
  final Color color;
  final double fontSize;

  const AnimatedScoreNumber({
    super.key,
    required this.score,
    this.color = AppColors.textPrimary,
    this.fontSize = 36,
  });

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<int>(
      tween: IntTween(begin: score, end: score),
      duration: AppTheme.normalDuration,
      builder: (context, value, child) {
        return Text(
          value.toString(),
          style: AppTheme.scoreStyle.copyWith(
            color: color,
            fontSize: fontSize,
          ),
        );
      },
    );
  }
}

/// Points earned popup animation
class PointsEarnedPopup extends StatelessWidget {
  final int points;

  const PointsEarnedPopup({
    super.key,
    required this.points,
  });

  @override
  Widget build(BuildContext context) {
    return Text(
      '+$points',
      style: AppTheme.scoreStyle.copyWith(
        color: AppColors.success,
        fontSize: 48,
      ),
    )
        .animate()
        .fadeIn(duration: AppTheme.fastDuration)
        .slideY(begin: 0.5, end: 0, curve: Curves.easeOutBack)
        .scale(begin: const Offset(0.5, 0.5), end: const Offset(1, 1))
        .then(delay: const Duration(seconds: 1))
        .fadeOut();
  }
}
