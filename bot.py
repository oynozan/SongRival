import os
import time
import uuid
import random
import asyncio
from game import Game
from bucket import Bucket
from wallet import Wallet
from asyncio import sleep
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    filters,
    Application,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
)

load_dotenv() # Take environment variables from .env.

# Instances
wallet = Wallet()
bucket = Bucket()

# Constants
FEE = 0.5 # Cut from every game

class Bot():
    def __init__(self):
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')

        self.withdrawData = {}
        self.gameInstances = {}
        self.bets = [0, 0.01, 0.05, 0.1, 0.25, 0.5, 1] # Bet amounts are in BNB
        self.matchmakingPool = {bet: [] for bet in self.bets}

        ## Bot commands
        self.application = Application.builder().token(self.BOT_TOKEN).build()

        # Callback query handler
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                CommandHandler("rules", self.rules),
                CommandHandler("deposit", self.deposit),
                CommandHandler("withdraw", self.withdraw),
            ],
            states = {
                "start": [
                    CallbackQueryHandler(self.start, pattern="^start$"),
                    CallbackQueryHandler(self.rules, pattern="^rules$"),
                    CallbackQueryHandler(self.newRace, pattern="^race$"),
                    CallbackQueryHandler(self.deposit, pattern="^deposit$"),
                    CallbackQueryHandler(self.answer, pattern="^answer_.*$"),
                    CallbackQueryHandler(self.withdraw, pattern="^withdraw$"),
                ],
                "betAmount": [
                    CallbackQueryHandler(self.start, pattern="^start$"),
                    CallbackQueryHandler(self.answer, pattern="^answer_.*$"),
                    CallbackQueryHandler(self.matchmaking, pattern="^bet_.*$"),
                ],
                "matchmaking": [
                    CallbackQueryHandler(self.stop, pattern="^stop$"),
                    CallbackQueryHandler(self.answer, pattern="^answer_.*$"),
                ],
                "withdraw_address": [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.withdrawAmount)
                ],
                "withdraw_amount": [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handleWithdraw)
                ],
            },
            fallbacks=[CommandHandler("rules", self.rules)],
        )

        self.application.add_handler(conv_handler)
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await Choices.start(update)
        return "start"

    async def rules(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await Helper.sendMessage(
            update,
            "*Rules*:\n\n" +
            "*Song Rival* is a game where you compete with other players to guess the song as fast as you can.\n\n" +
            "*1)* First, you gotta deposit some BNB to your wallet. You can skip this step if you want to play free games\n" +
            "*2)* Now you can start matchmaking. Select a bet amount and wait for a rival to compete against.\n" +
            "*3)* You will be sent a song. Listen to it and guess the song title.\n" +
            "*4)* If none of the players answer correctly, it's a draw. If one of the players answers correctly, they win the bet.\n" +
            "*5)* You have 120 seconds to answer. If you don't answer in time, you can't win. If both of you time out, it's a draw.\n" +
            "*6)* You can withdraw your earnings to your wallet anytime."
        )
        return "start"

    async def newRace(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await Choices.betAmount(update, self.bets)
        return "betAmount"

    def clear(self, uid):
        for i in range(len(self.matchmakingPool.keys())):
            matchmake = self.matchmakingPool[self.bets[i]]
            if uid in matchmake:
                # Get game ID by user ID
                gameID = Game.getGameIDFromPlayers(self.gameInstances.values(), uid)

                # Remove user from matchmaking pool
                self.matchmakingPool[self.bets[i]].remove(uid)

                # Remove game instance
                self.gameInstances.pop(gameID, None)

                return True
        return False

    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query is None:
            id = update.effective_chat.id
        else:
            query = update.callback_query
            await query.answer()
            id = query.message.chat_id

        clearResult = self.clear(id)

        if clearResult:
            await Helper.sendMessage(update, "Matchmaking stopped.") # Notify user
        else:
            await Helper.sendMessage(update, "You are not in a matchmaking pool.")

        return "start"

    async def matchmaking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        betAmount = float(query.data.split("_")[-1])

        if betAmount not in self.bets:
            await Helper.sendMessage(update, "Invalid bet amount.")
            return

        userID = query.message.chat_id

        # Check if user is already in the matchmaking pool
        for i in range(len(self.matchmakingPool.keys())):
            matchmake = self.matchmakingPool[self.bets[i]]
            if userID in matchmake:
                await Helper.sendMessage(update, "Already in the matchmaking pool.")
                return

        uid = update.effective_chat.id
        gameExists = Game.getGameIDFromPlayers(self.gameInstances.values(), uid)

        if gameExists:
            await Helper.sendMessage(update, "You are already in a game.")
            return

        # Check balance
        if (betAmount != 0):
            balance = wallet.getBalance(uid)
            if balance < betAmount:
                await Helper.sendMessage(update, "Insufficient balance.")
                return

        keyboard = [
            [InlineKeyboardButton("Stop Matchmaking", callback_data="stop")]
        ]

        await Helper.sendMessageWithButtons(
            update,
            "Matchmaking... Please wait.",
            keyboard
        )

        result = None

        # Matchmake the user
        if len(self.matchmakingPool[betAmount]) > 0:
            result = {
                "u1": self.matchmakingPool[betAmount].pop(0),
                "u2": uid,
                "bet": betAmount
            }
        else:
            self.matchmakingPool[betAmount].append(userID)

        print("Pool:", self.matchmakingPool)

        # A game has been found
        if result:
            # Start game for both parties
            await self.startMatch([result["u1"], result["u2"]], result["bet"])

        return "matchmaking"

    async def startMatch(self, players: list, betAmount: float):
        async def startGame(*args):
            await self.gameThread(*args)

        gameID = str(uuid.uuid4())
        self.gameInstances[gameID] = Game(gameID)
        game = self.gameInstances[gameID]
        game.createEmptyGame(players, betAmount)

        songForm = lambda song: song.split('/')[-1].split(".")[0]

        # Load songs from the bucket
        songs = bucket.loadByType("mp3")

        # Select a random song as answer
        correctSong = songForm(random.choice(songs))

        # Create random choices
        other_choices = random.sample([song for song in songs if song != correctSong], 4)
        other_choices = [songForm(song) for song in other_choices]
        songsPool = other_choices + [correctSong]

        # Shuffle the choices
        random.shuffle(songsPool)

        # Download selected song temporarily
        path = f"temp/temp_{correctSong}.mp3"
        bucket.downloadFile(f"songs/{correctSong}.mp3", path)

        tasks = [
            asyncio.create_task(startGame(gameID, players[0], correctSong, songsPool, path)),
            asyncio.create_task(startGame(gameID, players[1], correctSong, songsPool, path)),
        ]

        print("Game started for:", players, "\nAnswer:", correctSong)

        await asyncio.gather(*tasks)

    async def gameThread(self, gameID, player, correctSong, songsPool, path):
        print(player)
        await Helper.sendMessageToID(
            bot=self.application.bot,
            id=player,
            text="Match found! Starting game...\n\nStarting in *5* seconds."
        )

        for i in range(4, 0, -1):
            await sleep(1)
            await Helper.sendMessageToID(
                bot=self.application.bot,
                id=player,
                text=f"*{i}*"
            )

        game = self.gameInstances[gameID]
        game.start(correctSong, songsPool, path)

        # Send the song to the player
        await Helper.sendVoice(
            self.application.bot,
            player,
            path
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    option,
                    callback_data="answer_" + option
                )
            ] for option in game.convertToSongTitle(songsPool)
        ]

        await Helper.sendMessageToIDWithButtons(
            self.application.bot,
            player,
            "You have 120 seconds to answer",
            keyboard
        )

        async def timerLifecycle():
            response = True
            while response:
                await asyncio.sleep(10)
                response = await self.timerHandler(gameID, player)

        asyncio.create_task(timerLifecycle())

    async def answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        player = query.message.chat_id
        answer = query.data.split("_")[-1]

        gameID = Game.getGameIDFromPlayers(self.gameInstances.values(), player)
        game = self.gameInstances[gameID]

        if not game:
            await Helper.sendMessage(update, "Game not found.")
            return "start"

        # Check timeout - This will probably never happen
        if time.time() - game.ts > 120_000:
            await Helper.sendMessage(update, "Game has timed out.")
            return "start"

        # Check if user has already answered
        if player in game.answered:
            await Helper.sendMessage(update, "You have already answered.")
            return "start"

        # Check if other user has answered correctly
        if game.winner:
            await Helper.sendMessage(update, "Your rival has already answered correctly.")
            return "start"

        correctSong = game.convertToSongTitle(game.correctSong)
        correctForm = f"{game.artistOfSong(game.correctSong)} - {correctSong}"

        ## Check if the answer is correct
        # Correct answer
        if answer == correctSong:
            self.win(game, player)

            # Winner
            await Helper.sendMessage(
                update,
                f"Correct guess! You've won {game.betAmount} BNB\n\nWanna play again? /start"
                if game.betAmount != 0
                else "Correct guess! You've won.\n\nWanna play again? /start"
            )
            # Loser
            await Helper.sendMessageToID(
                self.application.bot,
                game.otherUser(player),
                "Your rival has guessed correctly, you have lost.\n" +
                f"Correct song was *{correctForm}*" +
                "\n\nWanna play again? /start"
            )
        # Incorrect answer
        else:
            if len(game.answered) == 0:
                # User Reply
                await Helper.sendMessage(
                    update,
                    "Wrong answer! Waiting for your rival's answer.\nIf they answer wrong too, it's a draw."
                )
                # Other User
                await Helper.sendMessageToID(
                    self.application.bot,
                    game.otherUser(player),
                    "Your opponent has answered before you. If they answer correctly, you lose."
                )
            else:
                # User Reply
                await Helper.sendMessage(
                    update,
                    "Wrong answer!\nYour rival also guessed incorrectly. it's a draw.\n" +
                    f"Correct song was *{correctForm}*"
                    "\n\nWanna play again? /start"
                )
                # Other User
                await Helper.sendMessageToID(
                    self.application.bot,
                    game.otherUser(player),
                    "Your rival has answered incorrectly. It's a draw.\n" +
                    f"Correct song was *{correctForm}*"
                    "\n\nWanna play again? /start"
                )
            # Update game instance
            game.answered.append(player)

        # End the game
        if len(game.answered) == 2:
            await game.end()

        return "start"

    async def timerHandler(self, gameID, player):
        game = self.gameInstances[gameID]
        ts = game.ts
        seconds = 0
        diff = time.time() - ts

        if player in game.answered or game.winner:
            return False

        # Game timeout - Guarenteed lose/draw
        if diff >= 120:
            # Check if other user has answered correctly
            if game.winner == game.otherUser(player):
                self.win(game, player)

                await Helper.sendMessageToID(
                    self.application.bot,
                    game.otherUser(player),
                    f"Your rival has timed out. You've won {game.betAmount} BNB\n\n"+
                    "Wanna play again? /start"
                    if game.betAmount != 0
                    else "Your rival has timed out. You've won.\n\n"+
                    "Wanna play again? /start"
                )
            elif len(game.answered) == 0:
                await Helper.sendMessageToID(
                    self.application.bot,
                    game.otherUser(player),
                    "Both players have timed out. It's a draw.\n\n" +
                    "Wanna play again? /start"
                )
            else:
                await Helper.sendMessageToID(
                    self.application.bot,
                    game.otherUser(player),
                    "Your rival has timed out. It's a draw.\n\n" +
                    "Wanna play again? /start"
                )

            await game.end()
            return False

        # Time notifications
        if diff > 60 and diff < 70: seconds = 60
        if diff > 90 and diff < 100: seconds = 30
        if diff > 110 and diff < 120: seconds = 10

        if seconds:
            await Helper.sendMessageToID(
                self.application.bot,
                player,
                f"You have {seconds} seconds left."
            )

        return True

    def win(self, game, player):
        # Update game instance
        game.answered.append(player)
        game.setWinner(player)

        ## Adjust balance
        # Send losers bet to the winner's wallet address
        if game.betAmount != 0:
            cutFee = game.betAmount * FEE
            res = wallet.withdraw(
                game.otherUser(player),
                wallet.getWallet(player)["address"],
                game.betAmount - cutFee
            )
            print(f"Transaction Hash: {res.tx_hash}")

            # Send fee to the fee address
            if res.tx_hash:
                wallet.withdraw(
                    game.otherUser(player),
                    os.getenv("FEE_ADDRESS"),
                    cutFee
                )

    async def deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await Choices.deposit(update)
        return "start"

    async def withdraw(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Show balance
        balance = wallet.getBalance(update.effective_chat.id)

        # Check if user is in a game
        if Game.getGameIDFromPlayers(self.gameInstances.values(), update.effective_chat.id):
            await Helper.sendMessage(update, "You cannot withdraw while in a game.")
            return "start"

        await Helper.sendMessage(update, f"Your balance is: *{balance}* BNB")

        # Ask for withdraw address
        await Helper.sendMessage(update, "Enter the BEP-20 address you want to withdraw to:")
        return "withdraw_address"

    async def withdrawAmount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        withdraw_address = update.message.text

        self.withdrawData[user_id] = {
            "address": withdraw_address
        }

        # Ask for withdraw amount
        await Helper.sendMessage(update, "Enter the amount you want to withdraw:")

        return "withdraw_amount"

    async def handleWithdraw(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        withdraw_amount = update.message.text

        self.withdrawData[user_id]["amount"] = withdraw_amount

        # Check balance
        try:
            if wallet.getBalance(user_id) < float(withdraw_amount):
                await Helper.sendMessage(update, "Insufficient balance.")
                return "start"
        except:
            await Helper.sendMessage(update, "Invalid amount.")
            return "start"

        # Start withdrawal
        await Helper.sendMessage(update, "Processing withdrawal...")

        try:
            res = wallet.withdraw(
                user_id,
                self.withdrawData[user_id]["address"],
                self.withdrawData[user_id]["amount"]
            )
        except Exception as e:
            await Helper.sendMessage(update, "An error occurred while processing the withdrawal.")
            return "start"

        hash = res.tx_hash

        await Helper.sendMessage(
            update,
            f"Waiting for transaction. Transaction hash: *{hash}*\n\nhttps://bscscan.com/tx/{hash}"
        )

        return "start"

class Choices:
    # Start the bot
    @staticmethod
    async def start(update: Update):
        keyboard = [
            [
                InlineKeyboardButton("Start Race", callback_data="race"),
            ],
            [
                InlineKeyboardButton("Rules", callback_data="rules")
            ],
            [
                InlineKeyboardButton("Deposit", callback_data="deposit"),
                InlineKeyboardButton("Withdraw", callback_data="withdraw")
            ]
        ]

        await Helper.sendMessageWithButtons(
            update,
            "Welcome to the *Song Rival*! Try to guess songs as fast as you can and earn BNB by competing with others." +
            "\n\n/rules: View the rules."+
            "\n/deposit: Deposit BNB to your wallet."+
            "\n/withdraw: Withdraw BNB from your wallet.",
            keyboard
        )

    # Ask for bet amount
    @staticmethod
    async def betAmount(update: Update, bets: list):
        keyboard = []
        row = []

        for i in range(len(bets)):
            bet = bets[i]
            row.append(
                InlineKeyboardButton(
                    f"{str(bet)} BNB" if bet != 0 else "Free Game",
                    callback_data="bet_" + str(bet)
                )
            )

            if i % 2 == 1:
                keyboard.append(row)
                row = []

        keyboard.append([InlineKeyboardButton("Cancel", callback_data="start")])

        await Helper.sendMessageWithButtons(
            update,
            "Select a bet amount:",
            keyboard
        )

    @staticmethod
    async def deposit(update: Update):
        address = wallet.getWallet(update.effective_chat.id)["address"]

        await Helper.sendMessage(
            update,
            "Your deposit address is:\n`" + address + "`\n\nSend *BNB* to this address to deposit to your wallet."
        )

class Helper:
    @staticmethod
    async def sendMessage(update: Update, text: str):
        await update.effective_chat.send_message(
            text,
            parse_mode='Markdown'
        )

    @staticmethod
    async def sendMessageToID(bot, id, text: str):
        await bot.send_message(
            chat_id=id,
            text=text,
            parse_mode='Markdown'
        )

    @staticmethod
    async def sendMessageWithButtons(update: Update, text: str, keyboard: list):
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.effective_chat.send_message(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    @staticmethod
    async def sendMessageToIDWithButtons(bot, id, text: str, keyboard: list):
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    @staticmethod
    async def reply(update: Update, text: str):
        await update.message.reply_text(
            text,
            parse_mode='Markdown'
        )

    @staticmethod
    async def replyWithButtons(update: Update, text: str, keyboard: list):
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    @staticmethod
    async def sendVoice(bot: Bot, id: str, file):
        await bot.send_voice(
            chat_id=id,
            voice=file
        )