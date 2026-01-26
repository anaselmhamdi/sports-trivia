import 'package:flutter/material.dart';

/// Sports Trivia "Stadium Pulse" color palette
/// Modern sports broadcast meets luxury editorial aesthetic
class AppColors {
  AppColors._();

  // Primary Palette
  static const Color voidBlack = Color(0xFF0D0D0F);
  static const Color surface = Color(0xFF1A1A1F);
  static const Color surfaceLight = Color(0xFF242429);
  static const Color electricCyan = Color(0xFF00F5D4);
  static const Color pulseOrange = Color(0xFFFF6B35);
  static const Color victoryGreen = Color(0xFF00FF87);
  static const Color lossRed = Color(0xFFFF3366);

  // Neutral Palette
  static const Color white = Color(0xFFFFFFFF);
  static const Color gray400 = Color(0xFF9CA3AF);
  static const Color gray500 = Color(0xFF6B7280);
  static const Color gray700 = Color(0xFF374151);
  static const Color gray900 = Color(0xFF111827);

  // Aliases for semantic usage
  static const Color background = voidBlack;
  static const Color primary = electricCyan;
  static const Color secondary = pulseOrange;
  static const Color success = victoryGreen;
  static const Color error = lossRed;
  static const Color textPrimary = white;
  static const Color textSecondary = gray500;

  // Timer urgency colors
  static const Color timerCalm = electricCyan;
  static const Color timerWarning = pulseOrange;
  static const Color timerUrgent = lossRed;

  // Glow effect colors (with opacity)
  static Color glowCyan = electricCyan.withValues(alpha: 0.3);
  static Color glowOrange = pulseOrange.withValues(alpha: 0.4);
  static Color glowRed = lossRed.withValues(alpha: 0.5);
  static Color glowGreen = victoryGreen.withValues(alpha: 0.4);

  /// Get timer color based on remaining seconds
  static Color getTimerColor(int remainingSeconds) {
    if (remainingSeconds > 30) {
      return timerCalm;
    } else if (remainingSeconds > 15) {
      return timerWarning;
    } else {
      return timerUrgent;
    }
  }

  /// Get timer glow color based on remaining seconds
  static Color getTimerGlow(int remainingSeconds) {
    if (remainingSeconds > 30) {
      return glowCyan;
    } else if (remainingSeconds > 15) {
      return glowOrange;
    } else {
      return glowRed;
    }
  }
}
