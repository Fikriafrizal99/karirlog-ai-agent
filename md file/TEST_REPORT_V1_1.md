# Test Report — KarirLog AI Agent V1.1

## Automated tests

Command:

```text
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result:

- Tests run: 33
- Passed: 33
- Failed: 0
- Errors: 0

V1.0 regression coverage tetap mencakup collector, parsing, deduplication, AI/rule analysis, decision guardrail, database migration, CV selection, Gmail OAuth workflow mock, portal assistant mock, scheduler, dan audit trail.

V1.1 coverage tambahan:

- Tiga folder berpasangan berdasarkan `profile_id`.
- CV selalu menjadi attachment pertama.
- Seluruh attachment profile masuk ke package dan Gmail MIME.
- Supporting document hanya ikut ketika diminta eksplisit.
- Dokumen sensitif ditahan.
- Duplicate SHA-256 tidak dilampirkan dua kali.
- Multiple CV pada satu profile menghasilkan review.
- Portal plan membaca seluruh package attachment.

## Migration test

- Legacy `path` CV berhasil disalin ke `documents/cv/{profile_id}`.
- `cv_library.json` dimigrasikan ke version 2.
- Settings Gmail dan field custom tetap dipertahankan.
- Backup konfigurasi berhasil dibuat.

## Live integration

Live Gmail API tidak dijalankan pada build environment karena credential dan OAuth token pengguna tidak disertakan. Gmail MIME dan delivery workflow diuji dengan service mock. Integrasi Gmail milik pengguna telah berhasil pada V1.0; patch V1.1 hanya mengubah sumber attachment menjadi package manifest.
