import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:scas_mobile/main.dart';

void main() {
  testWidgets('ScasApp builds without throwing', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: ScasApp()));
    await tester.pump();

    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
