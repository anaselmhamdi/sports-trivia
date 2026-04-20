import 'package:flutter/material.dart';
import '../models/grid.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';

/// Compact chip rendering a NBA Grid category on a row/col header.
///
/// Handles the three icon kinds:
///   - `logo` / `trophy` / `portrait`: icon image (asset or network URL) + label
///   - `text`: label only, no icon
class CategoryChip extends StatelessWidget {
  final GridCategory category;
  final double iconSize;
  final double maxWidth;

  const CategoryChip({
    super.key,
    required this.category,
    this.iconSize = 32,
    this.maxWidth = 110,
  });

  @override
  Widget build(BuildContext context) {
    final tooltip = category.description ?? category.displayName;
    return Tooltip(
      message: tooltip,
      child: Container(
        constraints: BoxConstraints(maxWidth: maxWidth),
        padding: const EdgeInsets.symmetric(
          horizontal: AppTheme.spaceXs,
          vertical: 2,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (category.iconKind != 'text' && category.iconUrl != null) ...[
              _CategoryIcon(url: category.iconUrl!, size: iconSize),
              const SizedBox(height: 4),
            ],
            Text(
              category.displayName,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
                height: 1.15,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CategoryIcon extends StatelessWidget {
  final String url;
  final double size;
  const _CategoryIcon({required this.url, required this.size});

  @override
  Widget build(BuildContext context) {
    final isAsset = url.startsWith('assets/');
    final placeholder = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: AppColors.surface,
        shape: BoxShape.circle,
      ),
      child: Icon(Icons.sports_basketball, size: size * 0.6, color: AppColors.textSecondary),
    );
    final img = isAsset
        ? Image.asset(
            url,
            width: size,
            height: size,
            errorBuilder: (_, __, ___) => placeholder,
          )
        : Image.network(
            url,
            width: size,
            height: size,
            errorBuilder: (_, __, ___) => placeholder,
          );
    return ClipOval(child: SizedBox(width: size, height: size, child: img));
  }
}
