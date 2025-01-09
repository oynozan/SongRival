import os
import time
import asyncio
from db import DB
from bucket import Bucket

# Instances
bucket = Bucket()

# Databases
db = DB("db/games.db")
songsDB = DB("db/downloader.db")

class Game:
    def __init__(self, id):
        # winner: True if user1 wins,
        #         False if user2 wins
        db.execute_query('''CREATE TABLE IF NOT EXISTS games (
                            id VARCHAR PRIMARY KEY,
                            u1 TEXT,
                            u2 TEXT,
                            bet DOUBLE,
                            answer VARCHAR,
                            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            winner BOOLEAN,
                            status VARCHAR DEFAULT "playing")''')

        self.songsPoolTitles = []
        self.activeQuestion = 0
        self.correctSong = None
        self.songsPool = None
        self.winner = None
        self.betAmount = 0
        self.answered = []
        self.players = []
        self.id = id
        self.ts = 0

    def createEmptyGame(self, players, betAmount):
        # Insert the game into the database
        db.insert("games", {
            "id": self.id,
            "u1": players[0],
            "u2": players[1],
            "bet": betAmount,
        })

        self.players = players
        self.betAmount = betAmount

    def start(self, correctSong, songsPool, path):
        self.correctSong = correctSong
        self.songsPool = songsPool
        self.ts = time.time()

        # Insert the game into the database
        gameObj = {
            "answer": self.correctSong,
        }

        db.update("games", gameObj, "id = ?", (self.id,))

    async def end(self):
        path = f"temp/temp_{self.correctSong}.mp3"

        # Check path, if not exists, it means the method is already called
        if not os.path.exists(path):
            return

        # Update game in DB
        gameObj = {
            "winner": True if self.winner == self.players[0] else False,
            "status": "finished"
        }
        db.update("games", gameObj, "id = ?", (self.id,))

        # Delete the temporary file
        async def removeTempFile():
            await asyncio.sleep(120)
            os.remove(path)
        asyncio.create_task(removeTempFile())

    def setWinner(self, winner):
        self.winner = winner

    def otherUser(self, userID):
        return self.players[0] if userID == self.players[1] else self.players[1]

    def convertToSongTitle(self, pool):
        newPool = []
        notList = False

        if type(pool) != list:
            pool = [pool]
            notList = True

        for song in pool:
            songData = songsDB.fetch_one("SELECT title FROM songs WHERE id = ?", (song,))
            newPool.append(songData["title"])

        self.songsPoolTitles = newPool

        if notList: return newPool[0]
        return newPool

    def artistOfSong(self, song):
        songData = songsDB.fetch_one("SELECT artist FROM songs WHERE id = ?", (song,))
        return songData["artist"]

    @staticmethod
    def getGameIDFromPlayers(instances, players):
        if type(players) != list:
            players = [players]
        for instance in instances:
            for player in players:
                if player not in instance.players:
                    break
            else:
                return instance.id
        return None

    @staticmethod
    def loadSongs():
        songs = songsDB.fetch_all("SELECT id FROM songs")
        return [song["id"] for song in songs]

    @staticmethod
    def downloadSong(song, path):
        bucket.downloadFile(f"songs/{song}.mp3", path)