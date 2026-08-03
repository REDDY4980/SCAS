import 'package:flutter/material.dart';

class SoilUploadScreen extends StatelessWidget {
  const SoilUploadScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Upload Soil Report')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          children: [
            Expanded(
              child: Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.green, width: 2),
                  borderRadius: BorderRadius.circular(16),
                  color: const Color(0xFFF1F8E9),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.cloud_upload, size: 64, color: Color(0xFF1B5E20)),
                    const SizedBox(height: 16),
                    const Text('Tap to Upload', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                    const Text('or choose from gallery', style: TextStyle(color: Colors.grey)),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1B5E20), foregroundColor: Colors.white),
                      onPressed: () {
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const SoilAnalysisResultScreen()));
                      },
                      child: const Text('Process OCR Analysis'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class SoilAnalysisResultScreen extends StatelessWidget {
  const SoilAnalysisResultScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Soil Analysis Result')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Soil Test Report Summary', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          _nutrientCard('Organic Carbon', '0.85%', 'Good', Colors.green),
          _nutrientCard('Nitrogen (N)', '325 kg/ha', 'High', Colors.blue),
          _nutrientCard('Phosphorus (P)', '28 kg/ha', 'Medium', Colors.orange),
          _nutrientCard('Potassium (K)', '410 kg/ha', 'High', Colors.green),
          const SizedBox(height: 24),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1B5E20), foregroundColor: Colors.white, padding: const EdgeInsets.all(16)),
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const AIDecisionDashboard()));
            },
            child: const Text('View AI Recommendation', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _nutrientCard(String title, String val, String status, Color color) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
              Text(val, style: const TextStyle(fontSize: 16, color: Colors.grey)),
            ]),
            Chip(label: Text(status, style: const TextStyle(color: Colors.white)), backgroundColor: color),
          ],
        ),
      ),
    );
  }
}

class AIDecisionDashboard extends StatelessWidget {
  const AIDecisionDashboard({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Decision Dashboard')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('Smart Insights for your farm', style: TextStyle(color: Colors.grey)),
          const SizedBox(height: 16),
          ListTile(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            tileColor: const Color(0xFFE8F5E9),
            leading: const Icon(Icons.eco, color: Color(0xFF1B5E20), size: 36),
            title: const Text('Best Crop: Groundnut', style: TextStyle(fontWeight: FontWeight.bold)),
            subtitle: const Text('High Profitability Rating'),
            trailing: const Icon(Icons.arrow_forward_ios, size: 16),
            onTap: () {},
          ),
          const SizedBox(height: 12),
          ListTile(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            tileColor: Colors.white,
            leading: const Icon(Icons.coronavirus, color: Colors.orange, size: 36),
            title: const Text('Disease Risk: Low', style: TextStyle(fontWeight: FontWeight.bold)),
            subtitle: const Text('No major threats detected'),
            trailing: const Icon(Icons.arrow_forward_ios, size: 16),
            onTap: () {},
          ),
        ],
      ),
    );
  }
}
