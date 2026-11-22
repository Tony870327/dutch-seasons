"""Fail-closed, read-only Google Sheets -> public JSON publisher.

A:Q retain editorial source; R:Z are explicit website fields. No date
inference from prose. Invalid approved rows stop the entire publication.
"""
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'festivals-data.json'
SHEET_ID = '1K4Z9_v0L7PBW6QSxLl912wODt4am1Z_43r7kZoaza6o'
SHEET_RANGE = "'節慶主資料'!A1:Z500"
KINDS = {'confirmed', 'fixed', 'estimated', 'historical', 'seasonal', 'weeklyFri', 'weeklyThu'}
CATEGORIES = {'傳統與民俗', '花卉與季節', '美食', '文化與藝術', '地方特色慶典'}
HEADERS = ['網站開始日期 ISO', '網站結束日期 ISO', '網站日期類型', '每週重複規則',
           '季節月份（逗號分隔）', '重點場次（中文）', '重點場次（英文）',
           '網站備註（中文）', '網站備註（英文）']
WEEKDAYS = {'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'}


def date_value(value, label):
    if not value:
        return None
    if not re.fullmatch(r'20\d\d-\d\d-\d\d', value):
        raise ValueError(f'{label}: date must use YYYY-MM-DD')
    return dt.date.fromisoformat(value)


def recurrence(value):
    if not value:
        return []
    result = []
    for part in value.split(';'):
        m = re.fullmatch(r'(MON|TUE|WED|THU|FRI|SAT|SUN)(?:@((?:0[1-9]|1[0-2])(?:-(?:0[1-9]|1[0-2]))?))?', part.strip())
        if not m:
            raise ValueError(f'Invalid weekly rule: {part}')
        months = None
        if m.group(2):
            a, _, b = m.group(2).partition('-')
            start, end = int(a), int(b or a)
            if end < start:
                raise ValueError('Weekly rule month range is reversed')
            months = list(range(start, end + 1))
        result.append({'weekday': m.group(1), 'months': months})
    return result


def validate_row(row, row_number):
    v = (row + [''] * 26)[:26]
    ident, nl, zh, en, city, province, months, typ, cats_raw, url = (x.strip() for x in v[:10])
    start_raw, end_raw, kind, weekly_raw, season_raw, highlight_zh, highlight_en, note_zh, note_en = (x.strip() for x in v[17:26])
    prefix = f'Row {row_number} ({ident or "missing ID"})'
    if not re.fullmatch(r'[FS]\d{2}-\d{2}', ident):
        raise ValueError(prefix + ': invalid ID')
    if not all([nl, zh, en, city, province, months, note_zh, note_en]):
        raise ValueError(prefix + ': missing required name, location, months, or bilingual notes')
    if typ not in {'festival', 'seasonal'} or kind not in KINDS:
        raise ValueError(prefix + ': invalid type or date kind')
    cats = [c.strip() for c in cats_raw.replace('，', ',').split(',') if c.strip()]
    if not cats or len(cats) != len(set(cats)) or any(c not in CATEGORIES for c in cats):
        raise ValueError(prefix + ': invalid categories')
    if url:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ValueError(prefix + ': official URL must use https')
    start, end = date_value(start_raw, prefix + ' start'), date_value(end_raw, prefix + ' end')
    if bool(start) != bool(end) or (start and end < start):
        raise ValueError(prefix + ': incomplete or reversed date range')
    if kind != 'seasonal' and not start:
        raise ValueError(prefix + ': dates required for nonseasonal events')
    if kind == 'seasonal' and not season_raw:
        raise ValueError(prefix + ': seasonal months required')
    if kind != 'seasonal' and season_raw:
        raise ValueError(prefix + ': seasonal months only valid for seasonal events')
    season_months = []
    if season_raw:
        for part in season_raw.split(','):
            part = part.strip()
            if not re.fullmatch(r'(?:[1-9]|1[0-2])', part):
                raise ValueError(prefix + ': invalid seasonal month')
            season_months.append(int(part))
        if len(season_months) != len(set(season_months)):
            raise ValueError(prefix + ': duplicate seasonal month')
    weekly = recurrence(weekly_raw)
    if kind in {'weeklyFri', 'weeklyThu'} and not weekly:
        raise ValueError(prefix + ': missing weekly rule')
    if kind not in {'weeklyFri', 'weeklyThu'} and weekly:
        raise ValueError(prefix + ': weekly rule on nonweekly event')
    if (highlight_zh and not highlight_en) or (highlight_en and not highlight_zh):
        raise ValueError(prefix + ': highlight must be bilingual')
    return {'id': ident, 'nl': nl, 'zh': zh, 'en': en, 'city': city,
            'province': province, 'months': months, 'start': start.isoformat() if start else '',
            'end': end.isoformat() if end else '', 'kind': kind, 'cats': cats,
            'url': url, 'note': note_zh, 'noteEn': note_en,
            'highlight': highlight_zh, 'highlightEn': highlight_en,
            'weeklyRules': weekly, 'seasonMonths': season_months}


def convert(values):
    if not values or len(values[0]) < 26 or values[0][0] != 'ID' or values[0][14] != '人工審核狀態' or values[0][17:26] != HEADERS:
        raise ValueError('Unexpected Google Sheets headers; refusing to publish')
    output, seen, errors = [], set(), []
    for n, raw in enumerate(values[1:], start=2):
        row = (raw + [''] * 26)[:26]
        if not any(str(x).strip() for x in row):
            continue
        if row[14].strip() != '已確認':
            continue
        try:
            item = validate_row(row, n)
            if item['id'] in seen:
                raise ValueError('Duplicate approved ID: ' + item['id'])
            seen.add(item['id'])
            output.append(item)
        except (ValueError, TypeError) as e:
            errors.append(str(e))
    if errors:
        raise ValueError('Validation failed; no files changed:\n' + '\n'.join(errors))
    if not output:
        raise ValueError('No approved events; refusing to overwrite')
    return sorted(output, key=lambda item: item['id'])


def fetch_rows():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    secret = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not secret:
        raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON secret is missing')
    info = json.loads(secret)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    url = ('https://sheets.googleapis.com/v4/spreadsheets/' + SHEET_ID +
           '/values/' + quote(SHEET_RANGE, safe='') + '?valueRenderOption=FORMATTED_VALUE')
    response = AuthorizedSession(credentials).get(url, timeout=30)
    response.raise_for_status()
    return response.json()['values']


def main():
    items = convert(fetch_rows())
    encoded = json.dumps(items, ensure_ascii=False, indent=2) + '\n'
    # Atomic replace, and only after all approved rows pass validation.
    temporary = OUTPUT.with_suffix('.json.tmp')
    temporary.write_text(encoded, encoding='utf-8')
    temporary.replace(OUTPUT)
    print(f'Published {len(items)} approved events')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
