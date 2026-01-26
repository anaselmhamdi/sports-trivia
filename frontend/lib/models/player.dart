/// Represents a player in the game
class Player {
  final String id;
  final String name;
  final int score;
  final bool isReady;
  final bool hasSubmittedClub;
  final String? selectedClub;

  const Player({
    required this.id,
    required this.name,
    this.score = 0,
    this.isReady = false,
    this.hasSubmittedClub = false,
    this.selectedClub,
  });

  Player copyWith({
    String? id,
    String? name,
    int? score,
    bool? isReady,
    bool? hasSubmittedClub,
    String? selectedClub,
  }) {
    return Player(
      id: id ?? this.id,
      name: name ?? this.name,
      score: score ?? this.score,
      isReady: isReady ?? this.isReady,
      hasSubmittedClub: hasSubmittedClub ?? this.hasSubmittedClub,
      selectedClub: selectedClub ?? this.selectedClub,
    );
  }

  factory Player.fromJson(Map<String, dynamic> json) {
    return Player(
      id: json['id'] as String,
      name: json['name'] as String,
      score: json['score'] as int? ?? 0,
      isReady: json['is_ready'] as bool? ?? false,
      hasSubmittedClub: json['has_submitted_club'] as bool? ?? false,
      selectedClub: json['selected_club'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'score': score,
      'is_ready': isReady,
      'has_submitted_club': hasSubmittedClub,
      'selected_club': selectedClub,
    };
  }

  @override
  String toString() => 'Player(id: $id, name: $name, score: $score)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Player && runtimeType == other.runtimeType && id == other.id;

  @override
  int get hashCode => id.hashCode;
}
