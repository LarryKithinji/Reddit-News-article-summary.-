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
        self.tokenizer = SimpleTokenizer(self.language)

    def generate_summary(self, content: str) -> Optional[str]:
        """Generates a concise summary using Sumy with custom tokenizer."""
        try:
            # Clean content to remove promotional text and ads
            cleaned_content = self._clean_content(content)
            
            # Use our custom tokenizer instead of NLTK
            parser = PlaintextParser.from_string(cleaned_content, self.tokenizer)
            summarizer = LsaSummarizer(Stemmer(self.language))
            summarizer.stop_words = get_stop_words(self.language)

            # Start with more sentences to reach 100-120 word target
            initial_sentence_count = 6
            sentences = summarizer(parser.document, initial_sentence_count)
            summary = ' '.join(str(sentence) for sentence in sentences)

            # Adjust summary length to meet 100-120 word requirement
            summary = self._adjust_summary_length(summary, cleaned_content)

            if summary and len(summary.split()) >= 100:
                return summary
            else:
                logger.warning("Summary generation failed or too short.")
                return None
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return None

    def _clean_content(self, content: str) -> str:
        """Remove promotional content and ads from the text."""
        # Remove common promotional phrases
        promotional_phrases = [
            r'subscribe to our newsletter',
            r'follow us on',
            r'share this article',
            r'read more at',
            r'visit our website',
            r'click here',
            r'advertisement',
            r'sponsored content',
            r'about the author',
            r'related articles',
            r'trending now',
            r'popular posts'
        ]
        
        cleaned = content
        for phrase in promotional_phrases:
            cleaned = re.sub(phrase, '', cleaned, flags=re.IGNORECASE)
        
        # Remove URLs
        cleaned = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', cleaned)
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned

    def _adjust_summary_length(self, summary: str, original_content: str) -> str:
        """Adjust summary to be between 100-120 words."""
        words = summary.split()
        word_count = len(words)
        
        if 100 <= word_count <= 120:
            return summary
        elif word_count < 100:
            # Try to get more content by increasing sentence count
            try:
                parser = PlaintextParser.from_string(original_content, self.tokenizer)
                summarizer = LsaSummarizer(Stemmer(self.language))
                summarizer.stop_words = get_stop_words(self.language)
                
                # Increase sentence count to get more words
                sentences = summarizer(parser.document, 8)
                extended_summary = ' '.join(str(sentence) for sentence in sentences)
                extended_words = extended_summary.split()
                
                if len(extended_words) >= 100:
                    # Trim to 120 words if too long
                    return ' '.join(extended_words[:120])
                else:
                    return extended_summary
            except:
                return summary
        else:
            # Trim to 120 words
            return ' '.join(words[:120])
    

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
            # Format the comment according to the specified template
            formatted_comment = self._format_comment(submission.title, summary)
            submission.reply(formatted_comment)
            logger.info(f"Comment posted successfully on submission {submission.id}")
            time.sleep(Config.COMMENT_DELAY)
        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")

    def _format_comment(self, title: str, summary: str) -> str:
        """Format the comment according to the specified template."""
        formatted_comment = f"""**Summary for "{title}"**

{summary}

^This ^is ^a ^TLDR ^bot ^for ^r/AfricaVoice!"""
        
        return formatted_comment

# Run the bot
if __name__ == "__main__":
    bot = RedditBot()
    bot.run("AfricaVoice")