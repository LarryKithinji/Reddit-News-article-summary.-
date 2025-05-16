import praw
import requests
import logging
import time
from datetime import datetime
from typing import Optional
import google.generativeai as genai
import trafilatura
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_bot_advanced.log', mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration class
class Config:
    REDDIT_CLIENT_ID = "UPmL7obZQuA0lBYPm3AjGw"
    REDDIT_CLIENT_SECRET = "uc8uPJxAigPIXtuf_hBMWIvPqCmnNQ"
    REDDIT_USER_AGENT = "CommentBot"
    REDDIT_USERNAME = "Agile-Drummer-1160"
    REDDIT_PASSWORD = "KePCCgt2minU1s1"
    GEMINI_API_KEY = "AIzaSyDYjIuQUoAxhbNnl1oKSm5cfdJJqJGN9TY"

    SUBREDDIT_NAME = "East_AfricanCommunity"
    RATE_LIMIT_REQUESTS = 5
    RATE_LIMIT_WINDOW = 60
    ERROR_RETRY_DELAY = 60
    API_ERROR_DELAY = 300
    NORMAL_DELAY = 30
    MIN_SUMMARY_LENGTH = 200
    MAX_RETRIES = 3
    ANTI_PAYWALL_URL = "https://smry.ai/?url="

# Analytics class
class ContentAnalytics:
    def __init__(self):
        self.extraction_attempts = {}
        self.extraction_successes = {}

    def log_attempt(self, domain: str, strategy: str, success: bool):
        if domain not in self.extraction_attempts:
            self.extraction_attempts[domain] = {}
            self.extraction_successes[domain] = {}
        if strategy not in self.extraction_attempts[domain]:
            self.extraction_attempts[domain][strategy] = 0
            self.extraction_successes[domain][strategy] = 0
        self.extraction_attempts[domain][strategy] += 1
        if success:
            self.extraction_successes[domain][strategy] += 1

# Content extractor class
class ContentExtractor:
    def __init__(self, analytics: ContentAnalytics):
        self.analytics = analytics
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0'
        })

    def extract_content(self, url: str) -> Optional[str]:
        # First, try the anti-paywall route
        content = self._try_antipaywall(url)
        if content:
            return content

        # If the anti-paywall route fails, fall back to standard extraction
        return self._try_normal_extraction(url)

    def _try_antipaywall(self, url: str) -> Optional[str]:
        try:
            antipaywall_url = f"{Config.ANTI_PAYWALL_URL}{url}"
            response = self.session.get(antipaywall_url)
            if response.status_code == 200:
                # Assuming Smry.ai returns the content as plain text
                return response.text
            else:
                logger.warning(f"Failed to extract via anti-paywall: {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Anti-paywall extraction failed: {e}")
            return None

    def _try_normal_extraction(self, url: str) -> Optional[str]:
        try:
            downloaded = trafilatura.fetch_url(url)
            content = trafilatura.extract(downloaded, include_comments=False)
            return content if content else None
        except Exception as e:
            logger.warning(f"Failed to extract content normally: {e}")
            return None

# Reddit Bot class
class RedditBot:
    def __init__(self):
        self.analytics = ContentAnalytics()
        self.extractor = ContentExtractor(self.analytics)
        genai.configure(api_key=Config.GEMINI_API_KEY)
        self.reddit = praw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            user_agent=Config.REDDIT_USER_AGENT,
            username=Config.REDDIT_USERNAME,
            password=Config.REDDIT_PASSWORD
        )
        self.processed_posts = set()

    def run(self):
        while True:
            try:
                subreddit = self.reddit.subreddit(Config.SUBREDDIT_NAME)
                for submission in subreddit.stream.submissions(skip_existing=True):
                    if submission.id not in self.processed_posts:
                        self._process_submission(submission)
                        self.processed_posts.add(submission.id)
                        time.sleep(Config.NORMAL_DELAY)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(Config.ERROR_RETRY_DELAY)

    def _process_submission(self, submission):
        try:
            content = self.extractor.extract_content(submission.url)
            if not content:
                logger.info(f"Content not found for {submission.url}. Falling back to title-based search.")
                summary = self._generate_summary_from_title(submission.title)
            else:
                summary = self._generate_summary(content)

            if summary:
                self._post_comment(submission, summary)
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}")

    def _generate_summary(self, content: str) -> Optional[str]:
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            prompt = f"Summarize this article:\n\n{content}"
            response = model.generate_content(prompt)
            return response.text if response else None
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

    def _generate_summary_from_title(self, title: str) -> Optional[str]:
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            prompt = f"Provide a concise summary of any relevant information about: {title}"
            response = model.generate_content(prompt)
            return response.text if response else None
        except Exception as e:
            logger.error(f"Error generating summary from title: {e}")
            return None

    def _post_comment(self, submission, summary: str):
        try:
            submission.reply(f"**Article Summary:**\n\n{summary}")
        except Exception as e:
            logger.error(f"Error posting comment: {e}")

# Run the bot
if __name__ == "__main__":
    bot = RedditBot()
    bot.run()