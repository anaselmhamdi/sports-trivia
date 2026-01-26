import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:confetti/confetti.dart';
import '../models/game_state.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../utils/image_helpers.dart';

/// Animated result reveal widget
/// Shows winner announcement, points, and valid answers
class ResultReveal extends StatefulWidget {
  final RoundResult result;
  final String? selfId;
  final int selfScore;
  final int opponentScore;
  final SportType sport;

  const ResultReveal({
    super.key,
    required this.result,
    this.selfId,
    required this.selfScore,
    required this.opponentScore,
    required this.sport,
  });

  @override
  State<ResultReveal> createState() => _ResultRevealState();
}

class _ResultRevealState extends State<ResultReveal> {
  late ConfettiController _confettiController;

  bool get _isWinner => widget.result.winnerId == widget.selfId;
  bool get _isDraw => widget.result.winnerId == null;

  @override
  void initState() {
    super.initState();
    _confettiController = ConfettiController(
      duration: const Duration(seconds: 3),
    );

    // Play confetti if winner
    if (_isWinner && !_isDraw) {
      Future.delayed(const Duration(milliseconds: 500), () {
        if (mounted) {
          _confettiController.play();
        }
      });
    }
  }

  @override
  void dispose() {
    _confettiController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.topCenter,
      children: [
        // Confetti
        ConfettiWidget(
          confettiController: _confettiController,
          blastDirectionality: BlastDirectionality.explosive,
          particleDrag: 0.05,
          emissionFrequency: 0.05,
          numberOfParticles: 20,
          gravity: 0.1,
          colors: const [
            AppColors.electricCyan,
            AppColors.victoryGreen,
            Colors.white,
          ],
        ),

        // Content
        SingleChildScrollView(
          padding: const EdgeInsets.all(AppTheme.spaceLg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Hero player image (if there's a winning answer with image)
              if (!_isDraw && widget.result.correctAnswerImageUrl != null)
                _HeroPlayerImage(
                  imageUrl: widget.result.correctAnswerImageUrl!,
                  playerName: widget.result.correctAnswer,
                  sport: widget.sport,
                ),

              // Winner announcement
              _WinnerAnnouncement(
                isWinner: _isWinner,
                isDraw: _isDraw,
                winnerName: widget.result.winnerName,
                isTimeout: widget.result.isTimeout,
              ),

              const SizedBox(height: AppTheme.spaceLg),

              // Points earned
              if (widget.result.pointsEarned > 0 && _isWinner)
                _PointsDisplay(points: widget.result.pointsEarned),

              const SizedBox(height: AppTheme.spaceLg),

              // Score comparison
              _ScoreComparison(
                selfScore: widget.selfScore,
                opponentScore: widget.opponentScore,
                isLeading: widget.selfScore > widget.opponentScore,
              ),

              const SizedBox(height: AppTheme.space2xl),

              // Valid answers reveal with images
              _ValidAnswersReveal(
                correctAnswer: widget.result.correctAnswer,
                validAnswers: widget.result.validAnswers,
                validAnswerDetails: widget.result.validAnswerDetails,
                sport: widget.sport,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// Hero player image with name
class _HeroPlayerImage extends StatelessWidget {
  final String imageUrl;
  final String playerName;
  final SportType sport;

  const _HeroPlayerImage({
    required this.imageUrl,
    required this.playerName,
    required this.sport,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: AppTheme.spaceLg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Player image
          ClipOval(
            child: SizedBox(
              width: 120,
              height: 120,
              child: Image.network(
                getProxiedImageUrl(imageUrl) ?? '',
                fit: BoxFit.cover,
                loadingBuilder: (context, child, loadingProgress) {
                  if (loadingProgress == null) return child;
                  return Container(
                    color: AppColors.surface,
                    child: Center(
                      child: _SportIcon(sport: sport, size: 48),
                    ),
                  );
                },
                errorBuilder: (context, error, stackTrace) {
                  debugPrint('Hero image load error for $imageUrl: $error');
                  return Container(
                    color: AppColors.surface,
                    child: Center(
                      child: _SportIcon(sport: sport, size: 48),
                    ),
                  );
                },
              ),
            ),
          ),
          const SizedBox(height: AppTheme.spaceMd),
          // Player name
          Text(
            playerName,
            style: AppTheme.h3Style.copyWith(
              color: AppColors.electricCyan,
              fontWeight: FontWeight.w600,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    )
        .animate()
        .fadeIn(duration: AppTheme.normalDuration)
        .scale(
          begin: const Offset(0.5, 0.5),
          end: const Offset(1, 1),
          curve: Curves.elasticOut,
          duration: AppTheme.slowDuration,
        );
  }
}

/// Sport icon fallback for when images aren't available
class _SportIcon extends StatelessWidget {
  final SportType sport;
  final double size;

  const _SportIcon({required this.sport, required this.size});

  @override
  Widget build(BuildContext context) {
    final icon = sport == SportType.nba ? Icons.sports_basketball : Icons.sports_soccer;
    return Icon(
      icon,
      size: size,
      color: AppColors.textSecondary,
    );
  }
}

class _WinnerAnnouncement extends StatelessWidget {
  final bool isWinner;
  final bool isDraw;
  final String? winnerName;
  final bool isTimeout;

  const _WinnerAnnouncement({
    required this.isWinner,
    required this.isDraw,
    this.winnerName,
    this.isTimeout = false,
  });

  @override
  Widget build(BuildContext context) {
    final String title;
    final String subtitle;
    final Color color;
    final IconData icon;

    if (isDraw) {
      title = 'TIME\'S UP!';
      subtitle = isTimeout ? 'No one got it in time' : 'It\'s a draw';
      color = AppColors.pulseOrange;
      icon = Icons.timer_off;
    } else if (isWinner) {
      title = 'VICTORY!';
      subtitle = 'You got it right!';
      color = AppColors.victoryGreen;
      icon = Icons.emoji_events;
    } else {
      title = 'DEFEAT';
      subtitle = '${winnerName ?? 'Opponent'} wins this round';
      color = AppColors.lossRed;
      icon = Icons.sentiment_dissatisfied;
    }

    return Column(
      children: [
        Icon(
          icon,
          size: 80,
          color: color,
        )
            .animate()
            .fadeIn(duration: AppTheme.normalDuration)
            .scale(
              begin: const Offset(0.5, 0.5),
              end: const Offset(1, 1),
              curve: Curves.elasticOut,
              duration: AppTheme.slowDuration,
            ),
        const SizedBox(height: AppTheme.spaceMd),
        Text(
          title,
          style: AppTheme.h1Style.copyWith(
            color: color,
            fontSize: 56,
          ),
        )
            .animate()
            .fadeIn(delay: const Duration(milliseconds: 200))
            .slideY(begin: 0.3, end: 0, curve: Curves.easeOutCubic),
        const SizedBox(height: AppTheme.spaceSm),
        Text(
          subtitle,
          style: AppTheme.bodyStyle.copyWith(
            color: AppColors.textSecondary,
          ),
        ).animate().fadeIn(delay: const Duration(milliseconds: 400)),
      ],
    );
  }
}

class _PointsDisplay extends StatelessWidget {
  final int points;

  const _PointsDisplay({required this.points});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceLg,
        vertical: AppTheme.spaceMd,
      ),
      decoration: BoxDecoration(
        color: AppColors.success.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: AppColors.success.withValues(alpha: 0.3)),
      ),
      child: Text(
        '+$points POINTS',
        style: AppTheme.scoreStyle.copyWith(
          color: AppColors.success,
        ),
      ),
    )
        .animate()
        .fadeIn(delay: const Duration(milliseconds: 600))
        .scale(
          begin: const Offset(0.8, 0.8),
          end: const Offset(1, 1),
          curve: Curves.elasticOut,
        );
  }
}

class _ScoreComparison extends StatelessWidget {
  final int selfScore;
  final int opponentScore;
  final bool isLeading;

  const _ScoreComparison({
    required this.selfScore,
    required this.opponentScore,
    required this.isLeading,
  });

  String get _statusText {
    final diff = selfScore - opponentScore;
    if (diff > 0) {
      return 'You\'re ahead by $diff!';
    } else if (diff < 0) {
      return 'Opponent leads by ${-diff}';
    } else {
      return 'It\'s tied!';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _ScoreBox(
                label: 'YOU',
                score: selfScore,
                isHighlighted: isLeading,
              ),
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppTheme.spaceLg,
                ),
                child: Text(
                  '-',
                  style: AppTheme.h2Style.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
              _ScoreBox(
                label: 'OPP',
                score: opponentScore,
                isHighlighted: opponentScore > selfScore,
              ),
            ],
          ),
          const SizedBox(height: AppTheme.spaceSm),
          Text(
            _statusText,
            style: AppTheme.captionStyle.copyWith(
              color: isLeading ? AppColors.success : AppColors.textSecondary,
            ),
          ),
        ],
      ),
    ).animate().fadeIn(delay: const Duration(milliseconds: 800));
  }
}

class _ScoreBox extends StatelessWidget {
  final String label;
  final int score;
  final bool isHighlighted;

  const _ScoreBox({
    required this.label,
    required this.score,
    required this.isHighlighted,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          label,
          style: AppTheme.captionStyle.copyWith(
            letterSpacing: 2,
            color: isHighlighted ? AppColors.primary : AppColors.textSecondary,
          ),
        ),
        const SizedBox(height: AppTheme.spaceXs),
        Text(
          score.toString(),
          style: AppTheme.scoreStyle.copyWith(
            color: isHighlighted ? AppColors.primary : AppColors.textPrimary,
            fontSize: 48,
          ),
        ),
      ],
    );
  }
}

class _ValidAnswersReveal extends StatelessWidget {
  final String correctAnswer;
  final List<String> validAnswers;
  final List<PlayerAnswer> validAnswerDetails;
  final SportType sport;

  const _ValidAnswersReveal({
    required this.correctAnswer,
    required this.validAnswers,
    required this.validAnswerDetails,
    required this.sport,
  });

  @override
  Widget build(BuildContext context) {
    // Use validAnswerDetails if available, otherwise fall back to strings
    final hasDetails = validAnswerDetails.isNotEmpty;
    final displayCount = hasDetails ? validAnswerDetails.length : (validAnswers.isEmpty ? 1 : validAnswers.length);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'VALID ANSWERS',
          style: AppTheme.captionStyle.copyWith(
            letterSpacing: 2,
          ),
        ).animate().fadeIn(delay: const Duration(milliseconds: 1000)),
        const SizedBox(height: AppTheme.spaceMd),
        Wrap(
          spacing: AppTheme.spaceSm,
          runSpacing: AppTheme.spaceSm,
          children: List.generate(displayCount, (index) {
            final delay = Duration(milliseconds: 1200 + (index * 100));

            if (hasDetails) {
              final detail = validAnswerDetails[index];
              return _AnswerChipWithImage(
                answer: detail.name,
                imageUrl: detail.imageUrl,
                sport: sport,
                delay: delay,
              );
            } else {
              final answer = validAnswers.isEmpty ? correctAnswer : validAnswers[index];
              return _AnswerChip(
                answer: answer,
                delay: delay,
              );
            }
          }),
        ),
      ],
    );
  }
}

class _AnswerChip extends StatelessWidget {
  final String answer;
  final Duration delay;

  const _AnswerChip({
    required this.answer,
    required this.delay,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceMd,
        vertical: AppTheme.spaceSm,
      ),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Text(
        answer,
        style: AppTheme.bodyStyle.copyWith(
          color: AppColors.textPrimary,
        ),
      ),
    )
        .animate()
        .fadeIn(delay: delay)
        .slideX(begin: -0.2, end: 0, curve: Curves.easeOutCubic);
  }
}

/// Answer chip with player thumbnail image
class _AnswerChipWithImage extends StatelessWidget {
  final String answer;
  final String? imageUrl;
  final SportType sport;
  final Duration delay;

  const _AnswerChipWithImage({
    required this.answer,
    this.imageUrl,
    required this.sport,
    required this.delay,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(
        left: AppTheme.spaceXs,
        right: AppTheme.spaceMd,
        top: AppTheme.spaceXs,
        bottom: AppTheme.spaceXs,
      ),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(AppTheme.radiusFull),
        border: Border.all(color: AppColors.gray700),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Player thumbnail
          ClipOval(
            child: SizedBox(
              width: 32,
              height: 32,
              child: imageUrl != null
                  ? Image.network(
                      getProxiedImageUrl(imageUrl) ?? '',
                      fit: BoxFit.cover,
                      loadingBuilder: (context, child, loadingProgress) {
                        if (loadingProgress == null) return child;
                        return Container(
                          color: AppColors.surface,
                          child: Center(
                            child: _SportIcon(sport: sport, size: 16),
                          ),
                        );
                      },
                      errorBuilder: (context, error, stackTrace) {
                        debugPrint('Image load error for $imageUrl: $error');
                        return Container(
                          color: AppColors.surface,
                          child: Center(
                            child: _SportIcon(sport: sport, size: 16),
                          ),
                        );
                      },
                    )
                  : Container(
                      color: AppColors.surface,
                      child: Center(
                        child: _SportIcon(sport: sport, size: 16),
                      ),
                    ),
            ),
          ),
          const SizedBox(width: AppTheme.spaceSm),
          // Player name
          Text(
            answer,
            style: AppTheme.bodyStyle.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    )
        .animate()
        .fadeIn(delay: delay)
        .slideX(begin: -0.2, end: 0, curve: Curves.easeOutCubic);
  }
}
