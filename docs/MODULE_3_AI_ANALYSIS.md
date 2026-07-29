# Module 3 — AI Job Analysis

## Komponen

### `analysis.py`

Menjalankan rule analysis, requirement extraction, seniority detection, scoring, dan final guardrail.

### `ai_provider.py`

Mengirim profil terbatas dan lowongan ke OpenAI Responses API. Respons diminta dalam JSON schema yang ketat.

### Merge strategy

Final score menggunakan 70% semantic AI score dan 30% deterministic score. Keputusan kemudian dihitung ulang dan dibatasi guardrail. AI recommendation hanya boleh mempertahankan atau membuat keputusan lebih konservatif; AI tidak dapat menaikkan final decision melewati guardrail.

## Analysis source

- `AI`: structured AI result berhasil.
- `RULE_ONLY`: AI sengaja dinonaktifkan.
- `RULE_FALLBACK`: AI direncanakan tetapi tidak tersedia/gagal.

## Hard guardrail

- Scam/payment marker → SKIP.
- Lead/manager atau pengalaman sangat tinggi → SKIP.
- Seniority mismatch → REVIEW atau SKIP.
- Hard requirement hilang → APPLY diturunkan menjadi REVIEW.
- Tiga atau lebih requirement hilang → REVIEW/SKIP.
