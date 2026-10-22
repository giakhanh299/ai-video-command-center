"""Delete only the seven tabs explicitly named by the owner, with backup."""
import datetime
import json
from pathlib import Path

import cleanup_douyin_sheet as sheets


def run():
    report = {'status': 'FAILED', 'deleted': [], 'errors': []}
    output = Path(__file__).resolve().parents[1] / 'outputs' / 'sheet_cleanup'
    output.mkdir(parents=True, exist_ok=True)
    for auth in ('service', 'oauth'):
        try:
            session = sheets.session(auth)
            before = sheets.api(session, 'GET', params={'includeGridData': 'true'})
            props = {p['properties']['sheetId']: p['properties']['title'] for p in before['sheets']}
            for ident, title in sheets.DELETE.items():
                if ident in props and props[ident] != title:
                    raise ValueError('TAB_ID_TITLE_MISMATCH')
            for ident, title in sheets.KEEP.items():
                if props.get(ident) != title:
                    raise ValueError('REQUIRED_TAB_MISMATCH')
            requests = [{'deleteSheet': {'sheetId': i}} for i in sheets.DELETE if i in props]
            if requests:
                backup = output / ('before_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + auth + '.json')
                backup.write_text(json.dumps(before, ensure_ascii=False), encoding='utf-8')
                report['backup'] = str(backup)
                sheets.api(session, 'POST', ':batchUpdate', json={'requests': requests})
            after = sheets.api(session, 'GET', params={'fields': 'sheets.properties'})
            remaining = {p['properties']['sheetId']: p['properties']['title'] for p in after['sheets']}
            if remaining != {i: n for i, n in props.items() if i not in sheets.DELETE}:
                raise ValueError('POST_DELETE_VERIFICATION_FAILED')
            report.update(status='SUCCESS', auth=auth,
                          deleted=[sheets.DELETE[i] for i in props if i in sheets.DELETE], remaining=remaining)
            break
        except Exception as exc:
            # Credential values and raw HTTP responses never enter this report.
            report['errors'].append({'auth': auth, 'type': type(exc).__name__,
                'reason': str(exc) if str(exc).startswith(('Google Sheets HTTP', 'OAuth refresh failed', 'TAB_', 'REQUIRED_', 'POST_')) else 'AUTH_OR_CONNECTION_FAILED'})
    (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    run()
