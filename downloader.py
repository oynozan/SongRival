"""
This scripts works at background to download songs using a Spotify downloader API
and store them in the DigitalOcean bucket.
"""

import asyncio
import requests
from db import DB
from bucket import Bucket
from data.artists import artists
from os import getenv, path, remove
from fake_useragent import UserAgent

ua = UserAgent()
bucket = Bucket()

db = DB("db/downloader.db")

async def main():
    print("Song downloader started...\n")

    # Initialize the Spotiyfy downloader API
    api = API()

    # Create tables if not exists
    db.execute_query('''CREATE TABLE IF NOT EXISTS artists (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL)''')

    db.execute_query('''CREATE TABLE IF NOT EXISTS songs (
                        id TEXT PRIMARY KEY,
                        artist TEXT NOT NULL,
                        title TEXT NOT NULL)''')

    for artist in artists:
        # Check if artist ID is in DB
        artistID = db.fetch_one("SELECT * FROM artists WHERE name = ?", (artist,))

        # Skip if artist ID is already in DB
        if artistID: continue
    
        # Get artist ID from the API
        artistID = api.getArtistByName(artist)
        if not artistID: continue

        # Get top songs from artist
        topTracks = api.getTopTracks(artistID)
        if not topTracks: continue

        for track in topTracks:
            # Check if song is already in DB
            song = db.fetch_one("SELECT * FROM songs WHERE id = ?", (track,))
            if song: continue

            # Download the song
            songTitle = await api.downloadSong(track)
            if not songTitle: continue

            # Store song in DB
            db.insert("songs", {"id": track, "artist": artist, "title": songTitle})

        # Store artist ID in DB
        db.insert("artists", {"name": artist, "id": artistID})

        await asyncio.sleep(5)

class API:
    def __init__(self):
        self.baseURL = "https://spotify-downloader9.p.rapidapi.com"
        self.headers =  {
            'x-rapidapi-key': getenv("RAPIDAPI_KEY"),
            'x-rapidapi-host': self.baseURL.split('//')[1]
        }

    def getArtistByName(self, name: str):
        queryString = {
            "q": name,
            "type": "artists",
            "limit": "1",
            "offset":"0",
        }

        response = requests.get(
            f"{self.baseURL}/search",
            headers=self.headers,
            params=queryString
        )

        try: obj = response.json()
        except: return None

        id = obj["data"]["artists"]["items"][0]["id"]

        if not id:
            return None
        return id

    def getTopTracks(self, artistID: str):
        queryString = {
            "id": artistID,
            "country": "US",
        }

        response = requests.get(
            f"{self.baseURL}/artistTopTracks",
            headers=self.headers,
            params=queryString
        )

        try: obj = response.json()
        except: return None
        return map(lambda track: track["id"], obj["data"]["tracks"])

    async def downloadSong(self, trackID: str):
        obj = {"success": False}
        retries = 1

        while not obj["success"] and retries < 4: # Max 12 retries
            await asyncio.sleep(40) # Wait for download link
            print("Retry: ", retries)

            queryString = {
                "songId": f"https://open.spotify.com/track/{trackID}",
            }

            response = requests.get(
                f"{self.baseURL}/downloadSong",
                headers=self.headers,
                params=queryString
            )

            try: obj = response.json()
            except: break

            print(obj)
            retries += 1

        if not obj["success"]:
            print(f"Failed to download, cannot get download link: {trackID}")
            return False

        link = obj["data"]["downloadLink"]
        
        headers = {
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": ua.chrome
        }
        downloadResponse = requests.get(
            link,
            stream=True,
            headers=headers
        )

        output_directory = "temp"
        output_filename = f"{trackID}.mp3"
        output_path = path.join(output_directory, output_filename)

        if downloadResponse.status_code != 200:
            print(f"Failed to download: {trackID}")
            return

        # Save the file
        with open(output_path, "wb") as file:
            for chunk in downloadResponse.iter_content(chunk_size=8192):
                file.write(chunk)

        # Upload file to bucket
        bucket.uploadFile(output_filename, output_path)

        # Remove file from temp folder
        remove(output_path)

        print(f"Downloaded: {trackID}")
        return obj["data"]["title"]

if __name__ == "__main__":
    asyncio.run(main())