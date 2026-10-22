import json
import requests

token_info = json.load(open('D:/0.1_FACE_BOOK/Lay video tiktok/gdrive_token.json'))
r = requests.post('https://oauth2.googleapis.com/token', data={
    'client_id': token_info['client_id'],
    'client_secret': token_info['client_secret'],
    'refresh_token': token_info['refresh_token'],
    'grant_type': 'refresh_token'
})
access_token = r.json()['access_token']
folder_id = '1fV0GyTCBblUHQIpJ1Kzsh6rho8oYwY8b'
files_res = requests.get(
    'https://www.googleapis.com/drive/v3/files',
    headers={'Authorization': f'Bearer {access_token}'},
    params={
        'q': f"'{folder_id}' in parents and trashed = false",
        'fields': 'files(id, name, size, createdTime)',
        'orderBy': 'createdTime desc'
    }
)
print("Files in Google Drive folder:")
for f in files_res.json().get('files', []):
    size_mb = round(int(f.get('size', 0)) / (1024 * 1024), 2) if f.get('size') else 'N/A'
    print(f"- {f['name']} ({size_mb} MB) [ID: {f['id']}] at {f['createdTime']}")
