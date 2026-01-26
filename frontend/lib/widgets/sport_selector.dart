import 'package:flutter/material.dart';
import '../models/game_state.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Sport selector toggle between NBA and Soccer
/// Features smooth sliding indicator animation
class SportSelector extends StatelessWidget {
  final SportType selectedSport;
  final ValueChanged<SportType> onSportChanged;

  const SportSelector({
    super.key,
    required this.selectedSport,
    required this.onSportChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Stack(
        children: [
          // Sliding indicator
          AnimatedAlign(
            alignment: selectedSport == SportType.nba
                ? Alignment.centerLeft
                : Alignment.centerRight,
            duration: AppTheme.fastDuration,
            curve: Curves.easeOutCubic,
            child: FractionallySizedBox(
              widthFactor: 0.5,
              child: Container(
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                  boxShadow: AppTheme.glowShadow(AppColors.primary),
                ),
              ),
            ),
          ),
          // Buttons
          Row(
            children: [
              Expanded(
                child: _SportButton(
                  sport: SportType.nba,
                  isSelected: selectedSport == SportType.nba,
                  onTap: () => onSportChanged(SportType.nba),
                ),
              ),
              Expanded(
                child: _SportButton(
                  sport: SportType.soccer,
                  isSelected: selectedSport == SportType.soccer,
                  onTap: () => onSportChanged(SportType.soccer),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SportButton extends StatelessWidget {
  final SportType sport;
  final bool isSelected;
  final VoidCallback onTap;

  const _SportButton({
    required this.sport,
    required this.isSelected,
    required this.onTap,
  });

  IconData get _icon {
    return sport == SportType.nba ? Icons.sports_basketball : Icons.sports_soccer;
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Container(
        height: 48,
        padding: const EdgeInsets.symmetric(horizontal: AppTheme.spaceMd),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedSwitcher(
              duration: AppTheme.fastDuration,
              child: Icon(
                _icon,
                key: ValueKey('${sport.name}_icon'),
                color: isSelected ? AppColors.voidBlack : AppColors.textSecondary,
                size: 24,
              ),
            ),
            const SizedBox(width: AppTheme.spaceSm),
            AnimatedDefaultTextStyle(
              duration: AppTheme.fastDuration,
              style: AppTheme.bodyStyle.copyWith(
                color: isSelected ? AppColors.voidBlack : AppColors.textSecondary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
              ),
              child: Text(sport.displayName),
            ),
          ],
        ),
      ),
    );
  }
}

/// Large sport card for visual selection
class SportCard extends StatelessWidget {
  final SportType sport;
  final bool isSelected;
  final VoidCallback onTap;

  const SportCard({
    super.key,
    required this.sport,
    required this.isSelected,
    required this.onTap,
  });

  IconData get _icon {
    return sport == SportType.nba ? Icons.sports_basketball : Icons.sports_soccer;
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: AppTheme.fastDuration,
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.all(AppTheme.spaceLg),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary.withValues(alpha: 0.1) : AppColors.surface,
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          border: Border.all(
            color: isSelected ? AppColors.primary : AppColors.gray700,
            width: isSelected ? 2 : 1,
          ),
          boxShadow: isSelected ? AppTheme.glowShadow(AppColors.primary) : null,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: AppTheme.fastDuration,
              padding: const EdgeInsets.all(AppTheme.spaceMd),
              decoration: BoxDecoration(
                color: isSelected
                    ? AppColors.primary.withValues(alpha: 0.2)
                    : AppColors.gray700.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(
                _icon,
                size: 48,
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: AppTheme.spaceMd),
            Text(
              sport.displayName,
              style: AppTheme.h3Style.copyWith(
                color: isSelected ? AppColors.primary : AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
