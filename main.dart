import 'package:flutter/material.dart';
import 'screens/splash_screen.dart';

void main() {
  runApp(const SCASApp());
}

class SCASApp extends StatelessWidget {
  const SCASApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SCAS - Smart Crop Advisory System',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1B5E20),
          primary: const Color(0xFF1B5E20),
          secondary: const Color(0xFF4CAF50),
          surface: const Color(0xFFF9FBF9),
        ),
        scaffoldBackgroundColor: const Color(0xFFF9FBF9),
        fontFamily: 'Inter',
      ),
      home: const SplashScreen(),
    );
  }
}
