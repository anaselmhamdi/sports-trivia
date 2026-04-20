/// Client-side representation of one cell in the NBA Grid 3x3 board.
class GridCell {
  final String? markedBy; // player id
  final String? symbol; // "X" or "O"
  final String? playerName;
  final String? playerImageUrl;

  const GridCell({
    this.markedBy,
    this.symbol,
    this.playerName,
    this.playerImageUrl,
  });

  bool get isEmpty => markedBy == null;

  factory GridCell.fromJson(Map<String, dynamic> json) => GridCell(
        markedBy: json['marked_by'] as String?,
        symbol: json['symbol'] as String?,
        playerName: json['player_name'] as String?,
        playerImageUrl: json['player_image_url'] as String?,
      );

  GridCell copyWith({
    String? markedBy,
    String? symbol,
    String? playerName,
    String? playerImageUrl,
  }) =>
      GridCell(
        markedBy: markedBy ?? this.markedBy,
        symbol: symbol ?? this.symbol,
        playerName: playerName ?? this.playerName,
        playerImageUrl: playerImageUrl ?? this.playerImageUrl,
      );
}

/// Category shown as a row/col header on the grid. The `iconKind` tells the UI
/// whether `iconUrl` is a bundled Flutter asset (`logo`/`trophy`/`portrait`)
/// or plain text (no icon; render label only).
class GridCategory {
  final String id;
  final String family; // team | award | draft | decade | stat | season_stat | team_count | coach | birthplace
  final String displayName;
  final String? description; // one-line clarification (eligibility rule)
  final String? iconUrl;
  final String iconKind; // logo | trophy | portrait | text

  const GridCategory({
    required this.id,
    required this.family,
    required this.displayName,
    this.description,
    this.iconUrl,
    this.iconKind = 'text',
  });

  factory GridCategory.fromJson(Map<String, dynamic> json) => GridCategory(
        id: json['id'] as String,
        family: json['family'] as String? ?? 'text',
        displayName: json['display_name'] as String,
        description: json['description'] as String?,
        iconUrl: json['icon_url'] as String?,
        iconKind: json['icon_kind'] as String? ?? 'text',
      );
}

class DrawProposal {
  final String proposerId;
  final double proposedAt;

  const DrawProposal({required this.proposerId, required this.proposedAt});

  factory DrawProposal.fromJson(Map<String, dynamic> json) => DrawProposal(
        proposerId: json['proposer_id'] as String,
        proposedAt: (json['proposed_at'] as num).toDouble(),
      );
}

/// Why a grid game ended. Mirrors backend `end_reason`.
///
/// `boardFull` means the board filled with no 3-in-a-row — that's a DRAW.
/// `clockOut` is kept only for back-compat with any lingering payloads; the
/// current backend never emits it (timer expiry just passes the turn).
enum GridEndReason {
  threeInRow,
  boardFull,
  drawAccepted,
  clockOut;

  static GridEndReason? fromBackendString(String? value) {
    switch (value) {
      case 'three_in_row':
        return GridEndReason.threeInRow;
      case 'board_full':
        return GridEndReason.boardFull;
      case 'draw_accepted':
        return GridEndReason.drawAccepted;
      case 'clock_out':
        return GridEndReason.clockOut;
      default:
        return null;
    }
  }
}
