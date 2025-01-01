import logging
import asyncio
from bot import Bot
from multiprocessing import Process
from downloader import main as Downloader

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def run_downloader():
    asyncio.run(Downloader())

if __name__ == "__main__":
    p1 = Process(target=Bot)
    p2 = Process(target=run_downloader)

    p1.start()
    p2.start()

    p1.join()
    p2.join()