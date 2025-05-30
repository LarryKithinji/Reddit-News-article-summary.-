import praw
import requests
import logging
import time
from typing import Optional
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

# 🔽 Fix: ensure punkt tokenizer is downloaded
import nltk
nltk.download('punkt', quiet=True)
# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("reddit_bot.log", mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration class
class Config:
    REDDIT_CLIENT_ID = "f7W8IqjORfzKsNqHVVSlJg"
    REDDIT_CLIENT_SECRET = "-5Cw-MH-7r4GICQGishtgKhYuW9ssg"
    REDDIT_USER_AGENT = "CommentBot"
    REDDIT_USERNAME = "Old-Star54"
    REDDIT_PASSWORD = "KePCCgt2minU1s1"
    COMMENT_DELAY = 120  # 2 minutes between comments
    SUBMISSION_DELAY = 60  # 1 minute between submission checks
    LANGUAGE = "english"  # Language for Sumy summarizer
    SENTENCES_COUNT = 4  # Number of sentences for summary

# Content extractor class
class ContentExtractor:
    def extract_content(self, url: str) -> Optional[str]:
        """Extracts main content from a webpage using BeautifulSoup."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract main content by focusing on paragraphs
                paragraphs = soup.find_all('p')
                content = ' '.join(p.get_text(strip=True) for p in paragraphs)

                # Validate extracted content length
                if len(content) > 100:
                    return content
                else:
                    logger.warning(f"Content too short after parsing: {len(content)} characters")
                    return None
            else:
                logger.warning(f"Failed to fetch content. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching or parsing content: {e}")
            return None

# Sumy Summarizer class
class SumySummarizer:
    def __init__(self):
        self.language = Config.LANGUAGE
        self.sentence_count = Config.SENTENCES_COUNT

    def generate_summary(self, content: str) -> Optional[str]:
        """Generates a concise summary using Sumy."""
        try:
            parser = PlaintextParser.from_string(content, Tokenizer(self.language))
            summarizer = LsaSummarizer(Stemmer(self.language))
            summarizer.stop_words = get_stop_words(self.language)

            # Extract summary sentences
            sentences = summarizer(parser.document, self.sentence_count)
            summary = ' '.join(str(sentence) for sentence in sentences)

            if summary:
                return summary
            else:
                logger.warning("Summary generation failed. Sumy returned no content.")
                return None
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

# Reddit Bot class
class RedditBot:
    def __init__(self):
        self.extractor = ContentExtractor()
        self.summarizer = SumySummarizer()
        self.reddit = praw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            user_agent=Config.REDDIT_USER_AGENT,
            username=Config.REDDIT_USERNAME,
            password=Config.REDDIT_PASSWORD,
        )
        self.last_submission_time = time.time()  # Keep track of the latest processed submission time

        # Authentication check
        try:
            me = self.reddit.user.me()
            logger.info(f"Successfully authenticated as: {me.name}")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")

    def run(self, subreddit_name: str):
        """Main loop to monitor the subreddit and process new submissions."""
        logger.info(f"Starting bot for subreddit: {subreddit_name}")
        subreddit = self.reddit.subreddit(subreddit_name)

        while True:
            try:
                for submission in subreddit.new(limit=10):
                    if submission.created_utc > self.last_submission_time:
                        self._process_submission(submission)
                        self.last_submission_time = submission.created_utc
                        time.sleep(Config.SUBMISSION_DELAY)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)

    def _process_submission(self, submission):
        """Processes a single submission, extracts content, and posts a summary."""
        try:
            logger.info(f"Processing submission: {submission.title} (ID: {submission.id})")
            content = self.extractor.extract_content(submission.url)

            if content:
                logger.info(f"Extracted content of length: {len(content)} characters")
                summary = self.summarizer.generate_summary(content)

                if summary:
                    logger.info(f"Generated summary: {summary[:60]}...")  # Log first 60 chars
                    self._post_comment(submission, summary)
                else:
                    logger.warning("Summary generation failed")
            else:
                logger.warning("Content extraction failed")
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)

    def _post_comment(self, submission, summary: str):
        """Posts a comment on the submission with the generated summary."""
        try:
            submission.reply(summary)
            logger.info(f"Comment posted successfully on submission {submission.id}")
            time.sleep(Config.COMMENT_DELAY)
        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")

# Run the bot
if __name__ == "__main__":
    bot = RedditBot()
    bot.run("AfricaVoice")