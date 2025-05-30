import praw
import requests
import logging
import time
import re
from typing import Optional
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

# Simple tokenizer to replace NLTK dependency
class SimpleTokenizer:
    """A simple tokenizer that splits text into sentences without NLTK dependency."""
    
    def __init__(self, language="english"):
        self.language = language
        # Common sentence ending patterns
        self.sentence_endings = re.compile(r'[.!?]+\s+')
    
    def to_sentences(self, text):
        """Split text into sentences using regex patterns."""
        # Clean up the text
        text = text.strip()
        if not text:
            return []
        
        # Split by sentence endings but keep the endings
        sentences = self.sentence_endings.split(text)
        
        # Filter out empty sentences and very short ones
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        return sentences
    
    def to_words(self, sentence):
        """Split sentence into words."""
        # Simple word tokenization
        words = re.findall(r'\b\w+\b', sentence.lower())
        return words

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
                
                # Remove unwanted elements that contain promotional content
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
                    element.decompose()
                
                # Remove elements with promotional/advertising classes/ids
                promotional_selectors = [
                    '[class*="ad"]', '[id*="ad"]', '[class*="advertisement"]',
                    '[class*="promo"]', '[class*="sponsor"]', '[class*="related"]',
                    '[class*="author-bio"]', '[class*="author-info"]', '[class*="share"]',
                    '[class*="social"]', '[class*="newsletter"]', '[class*="subscribe"]'
                ]
                
                for selector in promotional_selectors:
                    for element in soup.select(selector):
                        element.decompose()
                
                # Try to find main article content first
                article_content = None
                
                # Look for common article containers
                article_selectors = ['article', 'main', '[class*="content"]', '[class*="article"]', '[class*="post"]']
                for selector in article_selectors:
                    article_element = soup.select_one(selector)
                    if article_element:
                        paragraphs = article_element.find_all('p')
                        if len(paragraphs) >= 2:  # Must have at least 2 paragraphs
                            article_content = ' '.join(p.get_text(strip=True) for p in paragraphs)
                            break
                
                # Fallback to all paragraphs if no article container found
                if not article_content:
                    paragraphs = soup.find_all('p')
                    article_content = ' '.join(p.get_text(strip=True) for p in paragraphs)

                # Validate extracted content length
                if article_content and len(article_content) > 200:  # Increased minimum length
                    return article_content
                else:
                    logger.warning(f"Content too short after parsing: {len(article_content) if article_content else 0} characters")
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
        self.tokenizer = SimpleTokenizer(self.language)

    def generate_summary(self, content: str) -> Optional[str]:
        """Generates a concise summary using Sumy with custom tokenizer."""
        try:
            # Use our custom tokenizer instead of NLTK
            parser = PlaintextParser.from_string(content, self.tokenizer)
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
                    # Check if summary meets minimum word count, if not, skip posting
                    word_count = len(summary.split())
                    if word_count >= 30:  # Minimum threshold for meaningful summary
                        self._post_comment(submission, summary)
                    else:
                        logger.warning(f"Summary too short ({word_count} words), skipping post")
                else:
                    logger.warning("Summary generation failed")
            else:
                logger.warning("Content extraction failed")
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)

    def _post_comment(self, submission, summary: str):
        """Posts a comment on the submission with the generated summary."""
        try:
            # Format the comment according to the specified template
            formatted_comment = self._format_comment(submission.title, summary)
            submission.reply(formatted_comment)
            logger.info(f"Comment posted successfully on submission {submission.id}")
            time.sleep(Config.COMMENT_DELAY)
        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")
    
    def _format_comment(self, title: str, summary: str) -> str:
        """Formats the comment according to the specified template."""
        # Ensure summary is within word count limits (75-100 words)
        words = summary.split()
        if len(words) < 75:
            # If too short, keep the original summary
            formatted_summary = summary
        elif len(words) > 100:
            # If too long, truncate to 100 words
            formatted_summary = ' '.join(words[:100])
        else:
            formatted_summary = summary
        
        # Create the formatted comment
        formatted_comment = f"""TLDR for "{title}"

{formatted_summary}

*This *is *a *TLDR *bot *for *r/AfricaVoice!"""
        
        return formatted_comment

# Run the bot
if __name__ == "__main__":
    bot = RedditBot()
    bot.run("AfricaVoice")