import os
import requests
import google_auth_oauthlib.flow
import googleapiclient.discovery

# Define the scope for read-only access to your Google Photos library.
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']

def authenticate():
    # OAuth 2.0 Authentication
    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    credentials = flow.run_local_server(port=0)
    service = googleapiclient.discovery.build('photoslibrary', 'v1',
                                              credentials=credentials, static_discovery=False)
    return service

def list_albums(service):
    albums = []
    nextPageToken = None
    while True:
        results = service.albums().list(pageSize=50, pageToken=nextPageToken).execute()
        if 'albums' in results:
            albums.extend(results['albums'])
        nextPageToken = results.get('nextPageToken')
        if not nextPageToken:
            break
    return albums

def list_highlight_albums(service):
    # Filter albums that have "highlights" or "hyperlight" in the title (case-insensitive)
    all_albums = list_albums(service)
    highlight_albums = [
        album for album in all_albums 
        if ('highlights' in album.get('title', '').lower() or 
            'hyperlight' in album.get('title', '').lower())
    ]
    return highlight_albums

def download_album_photos(service, album_id, album_title, progress_callback=None):
    # Create downloads directory if it doesn't exist
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # Create a folder for this album inside downloads
    folder_name = os.path.join('downloads', album_title.replace(" ", "_"))
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    nextPageToken = None
    while True:
        # Search for media items in the album
        body = {
            'albumId': album_id,
            'pageSize': 50,
            'pageToken': nextPageToken
        }
        response = service.mediaItems().search(body=body).execute()
        media_items = response.get('mediaItems', [])
        for item in media_items:
            download_photo(item, folder_name)
            if progress_callback:
                progress_callback()  # update file progress after each file is downloaded
        nextPageToken = response.get('nextPageToken')
        if not nextPageToken:
            break

def download_photo(media_item, folder_name):
    file_name = media_item.get('filename')
    base_url = media_item.get('baseUrl')
    mime_type = media_item.get('mimeType', '')
    
    # Different parameters for videos vs images
    if 'video' in mime_type.lower():
        # For videos, use "=dv" to get the full video file
        url = base_url + "=dv"
    else:
        # For images, use "=d" to get the original quality
        url = base_url + "=d"
        
    print(f"Downloading {file_name} ({mime_type})")
    response = requests.get(url)
    if response.status_code == 200:
        file_path = os.path.join(folder_name, file_name)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f"Successfully downloaded {file_name}")
    else:
        print(f"Failed to download {file_name}: Status {response.status_code}")

def count_album_media_items(service, album_id):
    count = 0
    nextPageToken = None
    while True:
        body = {
            'albumId': album_id,
            'pageSize': 50,
            'pageToken': nextPageToken
        }
        response = service.mediaItems().search(body=body).execute()
        media_items = response.get('mediaItems', [])
        count += len(media_items)
        nextPageToken = response.get('nextPageToken')
        if not nextPageToken:
            break
    return count 