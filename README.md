# Dutch Seasons — full Google Sheets synchronization

The website reads `festivals-data.json` at runtime. GitHub Actions reads the private Google Sheet daily and commits a new JSON file **only after all approved rows validate**. This package does not change the existing Vercel project or domain.

## Editorial data

Source tab: `節慶主資料`. Original A:Q columns are preserved. The following new columns are authoritative for website publishing:

| Column | Meaning | Example |
|---|---|---|
| R | Start date, ISO text | `2027-02-06` |
| S | End date, ISO text | `2027-02-09` |
| T | Date kind | `confirmed`, `fixed`, `estimated`, `historical`, `seasonal`, `weeklyFri`, `weeklyThu` |
| U | Weekly recurrence | `FRI;TUE@07-08` (Friday year-round within R:S; July–August Tuesdays) |
| V | Seasonal months | `3,4` |
| W | Highlight, Chinese | `遊行` |
| X | Highlight, English | `Parade` |
| Y | Website note, Chinese | Reviewed Chinese copy |
| Z | Website note, English | Reviewed English copy |

A record is published only if column O is exactly `已確認`. Unapproved records are excluded. New approved records are supported directly: give them a unique ID, all required A:J fields, and R:Z website fields. The original editorial notes in L, M, P and Q are never published or overwritten. Changes to L/M alone do **not** change published dates or website notes: edit R:Z to publish them.

For a `seasonal` event, R:S may be blank, in which case V controls estimated months (not confirmed daily blooms). For a seasonal attraction with an official opening window, R:S can contain opening dates. For a `weeklyFri` or `weeklyThu` event, R:S and U are required. Recurrence weekdays use `MON TUE WED THU FRI SAT SUN`, separated by semicolons. A month restriction uses `@07-08` or `@07`. A regular dated event requires R:S.

## Security setup

1. Create a Google Cloud project and enable Google Sheets API.
2. Create a service account and a JSON key. Never upload or commit the key.
3. Share the Google Sheet with the service account `client_email` as **Viewer**.
4. GitHub repository > Settings > Secrets and variables > Actions > New repository secret: name it `GOOGLE_SERVICE_ACCOUNT_JSON`, and paste the complete JSON key.
5. GitHub repository > Actions > `Sync approved festivals from Google Sheets` > Run workflow. Confirm it passes. The daily schedule is 05:17 UTC.

Upload all files and folders in this package to the repository root, preserving `.github/workflows/sync-festivals.yml` and `scripts/sync_sheets.py`. GitHub may hide `.github` in some file pickers: verify the workflow file is present after upload.

## Validation and safety

- Approved rows must have unique IDs, required bilingual names/notes, allowed category labels, valid type, HTTPS official URLs (if provided), and valid date fields.
- Dates must be literal ISO text `YYYY-MM-DD`, valid calendar dates, with start no later than end.
- Highlights must have both languages or neither. Seasonal months and weekly recurrence syntax are checked.
- Any invalid approved row fails the entire sync before writing. Existing JSON and website remain unchanged.
- The script never translates automatically or verifies organizer announcements. Dates, highlights and bilingual descriptions must be reviewed before marking a row `已確認`.
- The public JSON contains only approved display data, not service account credentials or editorial private notes.

## Local tests

`python -m unittest discover -s scripts -p 'test_*.py' -v`

To view the site locally, run `python -m http.server 8000` in the repository root and open `http://localhost:8000`.
