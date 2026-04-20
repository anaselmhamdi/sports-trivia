import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/game_state.dart';
import '../models/grid.dart';
import '../providers/game_provider.dart';
import '../theme/app_colors.dart';
import '../theme/app_theme.dart';
import '../utils/image_helpers.dart';
import 'category_chip.dart';
import 'player_autocomplete.dart';

/// 3×3 NBA Grid board: category headers, cells, clocks, and controls.
///
/// Rendered inside `GameScreen` when `state.mode == GameMode.nbaGrid`.
class GridBoard extends ConsumerStatefulWidget {
  const GridBoard({super.key});

  @override
  ConsumerState<GridBoard> createState() => _GridBoardState();
}

class _GridBoardState extends ConsumerState<GridBoard> {
  (int, int)? _selectedCell;
  Timer? _clockTimer;

  @override
  void initState() {
    super.initState();
    // Tick once per second to refresh the displayed clock.
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _clockTimer?.cancel();
    super.dispose();
  }

  void _submit(String playerName) {
    final cell = _selectedCell;
    if (cell == null) return;
    final text = playerName.trim();
    if (text.isEmpty) return;
    ref.read(gameStateProvider.notifier).submitGridGuess(
          row: cell.$1,
          col: cell.$2,
          playerName: text,
        );
    setState(() => _selectedCell = null);
  }

  void _cancelSelection() {
    setState(() => _selectedCell = null);
  }

  void _skip() => ref.read(gameStateProvider.notifier).skipGridTurn();
  void _proposeDraw() => ref.read(gameStateProvider.notifier).proposeGridDraw();
  void _acceptDraw() =>
      ref.read(gameStateProvider.notifier).respondGridDraw(accept: true);
  void _declineDraw() =>
      ref.read(gameStateProvider.notifier).respondGridDraw(accept: false);

  /// Seconds remaining on the current turn (server-authoritative deadline,
  /// smoothed client-side between server updates).
  double _remainingSeconds(GameState state) {
    final deadline = state.turnDeadline;
    if (deadline == null) return 0.0;
    final nowSec = DateTime.now().millisecondsSinceEpoch / 1000.0;
    final remaining = deadline - nowSec;
    return remaining < 0 ? 0.0 : remaining;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(gameStateProvider);
    if (state.grid == null ||
        state.rowCategories == null ||
        state.colCategories == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final myId = state.self?.id ?? '';
    final isMyTurn = state.currentTurnPlayerId == myId;
    final drawProposal = state.drawProposal;
    final incomingDraw = drawProposal != null && drawProposal.proposerId != myId;

    return SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(
              horizontal: AppTheme.spaceLg,
              vertical: AppTheme.spaceMd,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _TurnTimerHeader(state: state, secondsLeft: _remainingSeconds(state)),
                const SizedBox(height: AppTheme.spaceMd),
                if (incomingDraw) ...[
                  _DrawProposalBanner(
                    proposerName: state.opponent?.name ?? 'Opponent',
                    onAccept: _acceptDraw,
                    onDecline: _declineDraw,
                  ),
                  const SizedBox(height: AppTheme.spaceMd),
                ],
                _BoardWithHeaders(
                  state: state,
                  selectedCell: _selectedCell,
                  onCellTap: isMyTurn
                      ? (row, col) {
                          final cell = state.grid![row][col];
                          if (!cell.isEmpty) return;
                          setState(() => _selectedCell = (row, col));
                        }
                      : null,
                ),
                const SizedBox(height: AppTheme.spaceMd),
                if (_selectedCell != null)
                  _GuessInput(
                    onSubmit: _submit,
                    onCancel: _cancelSelection,
                    rowCat: state.rowCategories![_selectedCell!.$1],
                    colCat: state.colCategories![_selectedCell!.$2],
                  ),
                const SizedBox(height: AppTheme.spaceMd),
                _ActionBar(
                  isMyTurn: isMyTurn,
                  drawPending: drawProposal != null,
                  onSkip: _skip,
                  onProposeDraw: _proposeDraw,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------- sub-widgets ----------

/// Single big countdown timer + turn indicator. Each turn gets a fresh 60s;
/// when it hits 0 the turn auto-skips to the opponent.
class _TurnTimerHeader extends StatelessWidget {
  final GameState state;
  final double secondsLeft;
  const _TurnTimerHeader({required this.state, required this.secondsLeft});

  @override
  Widget build(BuildContext context) {
    final self = state.self;
    final opp = state.opponent;
    if (self == null) return const SizedBox.shrink();
    final myId = self.id;
    final currentId = state.currentTurnPlayerId;
    final isMyTurn = currentId == myId;
    final currentPlayer = currentId == myId
        ? self
        : (currentId == opp?.id ? opp : null);
    final currentName = isMyTurn ? 'Your turn' : '${currentPlayer?.name ?? "Opponent"}\'s turn';
    final currentSymbol = state.playerSymbols?[currentId ?? ''];
    final color = AppColors.getTimerColor(secondsLeft.toInt());

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppTheme.spaceLg,
        vertical: AppTheme.spaceMd,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: color, width: 2),
        boxShadow: isMyTurn
            ? [BoxShadow(color: color.withValues(alpha: 0.25), blurRadius: 12)]
            : null,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              if (currentSymbol != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    currentSymbol,
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                ),
              const SizedBox(width: AppTheme.spaceMd),
              Text(
                currentName,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          Text(
            _formatClock(secondsLeft),
            style: TextStyle(
              fontSize: 34,
              fontFeatures: const [FontFeature.tabularFigures()],
              fontWeight: FontWeight.bold,
              color: color,
              height: 1,
            ),
          ),
        ],
      ),
    );
  }

  String _formatClock(double seconds) {
    final s = seconds.clamp(0, 999).toInt();
    final m = s ~/ 60;
    final r = s % 60;
    return '${m.toString().padLeft(2, '0')}:${r.toString().padLeft(2, '0')}';
  }
}

class _BoardWithHeaders extends StatelessWidget {
  final GameState state;
  final (int, int)? selectedCell;
  final void Function(int row, int col)? onCellTap;
  const _BoardWithHeaders({
    required this.state,
    required this.selectedCell,
    required this.onCellTap,
  });

  @override
  Widget build(BuildContext context) {
    final grid = state.grid!;
    final rows = state.rowCategories!;
    final cols = state.colCategories!;
    return LayoutBuilder(
      builder: (context, constraints) {
        // Use the full available width (capped by the outer 820px constraint).
        // Row-header column gets a narrower strip than cells so cells dominate.
        final total = constraints.maxWidth;
        final headerColWidth = (total * 0.18).clamp(96.0, 150.0);
        final cellSize = (total - headerColWidth) / 3;
        final headerRowHeight = (cellSize * 0.42).clamp(72.0, 110.0);

        return Column(
          children: [
            // Column headers row
            Row(
              children: [
                SizedBox(width: headerColWidth, height: headerRowHeight),
                for (var c = 0; c < 3; c++)
                  SizedBox(
                    width: cellSize,
                    height: headerRowHeight,
                    child: _HeaderCell(
                      category: cols[c],
                      maxWidth: cellSize - 8,
                      maxHeight: headerRowHeight - 4,
                    ),
                  ),
              ],
            ),
            // Grid rows
            for (var r = 0; r < 3; r++)
              Row(
                children: [
                  SizedBox(
                    width: headerColWidth,
                    height: cellSize,
                    child: _HeaderCell(
                      category: rows[r],
                      maxWidth: headerColWidth - 8,
                      maxHeight: cellSize - 4,
                    ),
                  ),
                  for (var c = 0; c < 3; c++)
                    SizedBox(
                      width: cellSize,
                      height: cellSize,
                      child: _Cell(
                        cell: grid[r][c],
                        symbol: grid[r][c].symbol,
                        selected: selectedCell != null &&
                            selectedCell!.$1 == r &&
                            selectedCell!.$2 == c,
                        onTap:
                            onCellTap == null ? null : () => onCellTap!(r, c),
                      ),
                    ),
                ],
              ),
          ],
        );
      },
    );
  }
}

class _HeaderCell extends StatelessWidget {
  final GridCategory category;
  final double maxWidth;
  final double maxHeight;
  const _HeaderCell({
    required this.category,
    required this.maxWidth,
    required this.maxHeight,
  });

  @override
  Widget build(BuildContext context) {
    final iconSize = (maxHeight * 0.5).clamp(28.0, 52.0);
    return Padding(
      padding: const EdgeInsets.all(4),
      child: Center(
        child: CategoryChip(
          category: category,
          iconSize: iconSize,
          maxWidth: maxWidth,
        ),
      ),
    );
  }
}

class _Cell extends StatelessWidget {
  final GridCell cell;
  final String? symbol;
  final bool selected;
  final VoidCallback? onTap;
  const _Cell({
    required this.cell,
    required this.symbol,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final isX = symbol == 'X';
    final accent = isX ? AppColors.electricCyan : AppColors.pulseOrange;
    final tappable = onTap != null && cell.isEmpty;
    return Padding(
      padding: const EdgeInsets.all(4),
      child: Material(
        color: selected
            ? AppColors.surfaceLight
            : cell.isEmpty
                ? AppColors.surface
                : AppColors.voidBlack,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppTheme.radiusMd),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppTheme.radiusMd),
              border: Border.all(
                color: selected
                    ? AppColors.primary
                    : cell.isEmpty
                        ? (tappable
                            ? AppColors.gray700
                            : AppColors.gray800)
                        : accent.withValues(alpha: 0.6),
                width: selected ? 2 : 1,
              ),
            ),
            child: cell.isEmpty
                ? Center(
                    child: tappable
                        ? const Icon(
                            Icons.add,
                            color: AppColors.gray700,
                            size: 24,
                          )
                        : null,
                  )
                : _MarkedCellContent(cell: cell, accent: accent),
          ),
        ),
      ),
    );
  }
}

class _MarkedCellContent extends StatelessWidget {
  final GridCell cell;
  final Color accent;
  const _MarkedCellContent({required this.cell, required this.accent});

  @override
  Widget build(BuildContext context) {
    // NBA.com CDN doesn't serve CORS headers to web — route through the
    // existing /api/image/proxy endpoint so Image.network can decode it.
    final proxied = getProxiedImageUrl(cell.playerImageUrl);
    return Stack(
      fit: StackFit.expand,
      children: [
        if (proxied != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(AppTheme.radiusSm - 1),
            child: Image.network(
              proxied,
              fit: BoxFit.cover,
              alignment: const Alignment(0, -0.2), // head-up framing
              errorBuilder: (_, __, ___) => Container(color: AppColors.surface),
            ),
          ),
        // Soft bottom gradient so the name stays readable without hiding the face.
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          height: 40,
          child: DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.vertical(
                bottom: Radius.circular(AppTheme.radiusSm - 1),
              ),
              gradient: LinearGradient(
                begin: Alignment.bottomCenter,
                end: Alignment.topCenter,
                colors: [
                  AppColors.voidBlack.withValues(alpha: 0.85),
                  AppColors.voidBlack.withValues(alpha: 0.0),
                ],
              ),
            ),
          ),
        ),
        // Symbol badge top-left (on a small chip so it reads against any headshot)
        Positioned(
          top: 4,
          left: 4,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: AppColors.voidBlack.withValues(alpha: 0.75),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(
              cell.symbol ?? '',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: accent,
                height: 1,
              ),
            ),
          ),
        ),
        // Player name bottom
        Positioned(
          left: 4,
          right: 4,
          bottom: 4,
          child: Text(
            cell.playerName ?? '',
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              color: AppColors.white,
              height: 1.1,
            ),
          ),
        ),
      ],
    );
  }
}

class _GuessInput extends StatelessWidget {
  final void Function(String playerName) onSubmit;
  final VoidCallback onCancel;
  final GridCategory rowCat;
  final GridCategory colCat;

  const _GuessInput({
    required this.onSubmit,
    required this.onCancel,
    required this.rowCat,
    required this.colCat,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  '${rowCat.displayName}  ×  ${colCat.displayName}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                    fontSize: 14,
                  ),
                ),
              ),
              IconButton(
                onPressed: onCancel,
                icon: const Icon(Icons.close, size: 18),
                tooltip: 'Cancel',
              ),
            ],
          ),
          if (rowCat.description != null || colCat.description != null) ...[
            const SizedBox(height: AppTheme.spaceSm),
            _CategoryClarification(cat: rowCat),
            if (rowCat.description != null && colCat.description != null)
              const SizedBox(height: 4),
            _CategoryClarification(cat: colCat),
          ],
          const SizedBox(height: AppTheme.spaceSm),
          PlayerAutocomplete(
            sport: 'nba',
            onSubmitted: onSubmit,
            onCancelled: onCancel,
          ),
        ],
      ),
    );
  }
}

class _CategoryClarification extends StatelessWidget {
  final GridCategory cat;
  const _CategoryClarification({required this.cat});

  @override
  Widget build(BuildContext context) {
    if (cat.description == null) return const SizedBox.shrink();
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.info_outline, size: 14, color: AppColors.primary),
        const SizedBox(width: 6),
        Expanded(
          child: RichText(
            text: TextSpan(
              style: const TextStyle(fontSize: 12, height: 1.3),
              children: [
                TextSpan(
                  text: '${cat.displayName}: ',
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary,
                  ),
                ),
                TextSpan(
                  text: cat.description!,
                  style: const TextStyle(color: AppColors.textSecondary),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _ActionBar extends StatelessWidget {
  final bool isMyTurn;
  final bool drawPending;
  final VoidCallback onSkip;
  final VoidCallback onProposeDraw;

  const _ActionBar({
    required this.isMyTurn,
    required this.drawPending,
    required this.onSkip,
    required this.onProposeDraw,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: isMyTurn ? onSkip : null,
            icon: const Icon(Icons.skip_next),
            label: const Text('SKIP'),
          ),
        ),
        const SizedBox(width: AppTheme.spaceSm),
        Expanded(
          child: OutlinedButton.icon(
            onPressed: drawPending ? null : onProposeDraw,
            icon: const Icon(Icons.handshake_outlined),
            label: const Text('DRAW'),
          ),
        ),
      ],
    );
  }
}

class _DrawProposalBanner extends StatelessWidget {
  final String proposerName;
  final VoidCallback onAccept;
  final VoidCallback onDecline;
  const _DrawProposalBanner({
    required this.proposerName,
    required this.onAccept,
    required this.onDecline,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spaceMd),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusMd),
        border: Border.all(color: AppColors.pulseOrange),
      ),
      child: Column(
        children: [
          Text(
            '$proposerName proposed a draw',
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: AppTheme.spaceSm),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: onDecline,
                  child: const Text('DECLINE'),
                ),
              ),
              const SizedBox(width: AppTheme.spaceSm),
              Expanded(
                child: ElevatedButton(
                  onPressed: onAccept,
                  child: const Text('ACCEPT'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
