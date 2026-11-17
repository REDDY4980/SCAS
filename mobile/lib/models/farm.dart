/// Matches app/schemas/farm.py::FarmOut exactly.
class Farm {
  final String id;
  final String userId;
  final String farmName;
  final String state;
  final String district;
  final String? village;
  final double? latitude;
  final double? longitude;
  final String? soilType;
  final double? areaAcres;
  final String? locationSource; // gps | district | state | null
  final double? locationAccuracyM;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Farm({
    required this.id,
    required this.userId,
    required this.farmName,
    required this.state,
    required this.district,
    this.village,
    this.latitude,
    this.longitude,
    this.soilType,
    this.areaAcres,
    this.locationSource,
    this.locationAccuracyM,
    required this.createdAt,
    required this.updatedAt,
  });

  bool get hasCoordinates => latitude != null && longitude != null;
  bool get hasGps => locationSource == 'gps';

  factory Farm.fromJson(Map<String, dynamic> json) {
    return Farm(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      farmName: json['farm_name'] as String,
      state: json['state'] as String,
      district: json['district'] as String,
      village: json['village'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      soilType: json['soil_type'] as String?,
      areaAcres: (json['area_acres'] as num?)?.toDouble(),
      locationSource: json['location_source'] as String?,
      locationAccuracyM: (json['location_accuracy_m'] as num?)?.toDouble(),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toCreateJson() => {
        'farm_name': farmName,
        'state': state,
        'district': district,
        if (village != null) 'village': village,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (soilType != null) 'soil_type': soilType,
        if (areaAcres != null) 'area_acres': areaAcres,
        if (latitude != null && locationAccuracyM != null) 'location_accuracy_m': locationAccuracyM,
      };
}
