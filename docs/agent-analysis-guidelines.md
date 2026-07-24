# Agent analysis guidelines

Google Health Agent provides observations and mathematics; the consuming agent may interpret
them with clear uncertainty.

1. Start with data quality, then the overview.
2. Prefer the user's own median/IQR/MAD history over population thresholds.
3. Treat sleep, HRV, resting heart rate, respiratory rate, oxygen saturation, temperature, and
   activity as related but distinct signals.
4. Separate observed facts, statistical comparisons, hypotheses, and recommendations.
5. One unusual day is not a trend.
6. Missing data is not zero and should reduce confidence.
7. Check timezone/source changes and overlapping step sources.
8. Request bounded deeper history only when aggregation is insufficient.
9. Do not diagnose disease or characterize a statistical anomaly as a medical abnormality.
10. Encourage appropriate professional care only as general safety guidance, not diagnosis.

