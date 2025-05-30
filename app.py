import praw
import requests
import logging
import time
import re
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words
import urllib.parse

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

# Google News extractor class
class GoogleNewsExtractor:
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search"
    
    def get_related_news(self, query: str, exclude_url: str = None, max_results: int = 2) -> List[Dict[str, str]]:
        """Extract related news from Google News RSS, excluding the original URL."""
        try:
            # Clean and encode the query
            clean_query = re.sub(r'[^\w\s]', '', query)
            encoded_query = urllib.parse.quote(clean_query)
            
            # Construct Google News RSS URL
            params = {
                'q': clean_query,
                'hl': 'en-US',
                'gl': 'US',
                'ceid': 'US:en'
            }
            
            url = f"{self.base_url}?{'&'.join([f'{k}={urllib.parse.quote(str(v))}' for k, v in params.items()])}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                items = soup.find_all('item')
                
                news_links = []
                for item in items:
                    title = item.find('title')
                    link = item.find('link')
                    
                    if title and link:
                        # Extract actual URL from Google redirect
                        actual_url = self._extract_actual_url(link.text)
                        
                        # Skip if this is the same as the original submission URL
                        if exclude_url and self._urls_match(actual_url, exclude_url):
                            continue
                            
                        # Skip if URL contains the original domain to avoid duplicates
                        if exclude_url and self._same_domain(actual_url, exclude_url):
                            continue
                        
                        news_links.append({
                            'title': title.text.strip(),
                            'url': actual_url
                        })
                        
                        # Stop when we have enough results
                        if len(news_links) >= max_results:
                            break
                
                return news_links
            else:
                logger.warning(f"Failed to fetch Google News. Status code: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching Google News: {e}")
            return []
    
    def _urls_match(self, url1: str, url2: str) -> bool:
        """Check if two URLs are essentially the same."""
        try:
            # Normalize URLs for comparison
            url1_clean = re.sub(r'^https?://(www\.)?', '', url1.lower().strip('/'))
            url2_clean = re.sub(r'^https?://(www\.)?', '', url2.lower().strip('/'))
            return url1_clean == url2_clean
        except:
            return False
    
    def _same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain."""
        try:
            from urllib.parse import urlparse
            domain1 = urlparse(url1).netloc.lower().replace('www.', '')
            domain2 = urlparse(url2).netloc.lower().replace('www.', '')
            return domain1 == domain2
        except:
            return False
    
    def _extract_actual_url(self, google_url: str) -> str:
        """Extract actual URL from Google redirect URL."""
        try:
            # Google News URLs often contain the actual URL as a parameter
            if 'url=' in google_url:
                return urllib.parse.unquote(google_url.split('url=')[1].split('&')[0])
            else:
                return google_url
        except:
            return google_url

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
        """Adjust summary to be between 100-110 words and fix grammar."""
        words = summary.split()
        word_count = len(words)
        
        if 100 <= word_count <= 110:
            return self._fix_grammar(summary)
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
                    # Trim to 110 words if too long
                    final_summary = ' '.join(extended_words[:110])
                    return self._fix_grammar(final_summary)
                else:
                    return self._fix_grammar(extended_summary)
            except:
                return self._fix_grammar(summary)
        else:
            # Trim to 110 words
            trimmed_summary = ' '.join(words[:110])
            return self._fix_grammar(trimmed_summary)
    
    def _fix_grammar(self, text: str) -> str:
        """Fix common grammatical errors in the summary."""
        # Fix spacing issues
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Ensure proper sentence capitalization
        sentences = re.split(r'(?<=[.!?])\s+', text)
        fixed_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                # Capitalize first letter of each sentence
                sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
                
                # Fix common issues
                sentence = re.sub(r'\s+([.!?,:;])', r'\1', sentence)  # Remove space before punctuation
                sentence = re.sub(r'([.!?])\s*([a-z])', r'\1 \2', sentence)  # Add space after punctuation
                sentence = re.sub(r'\s+', ' ', sentence)  # Multiple spaces to single
                
                fixed_sentences.append(sentence)
        
        # Join sentences properly
        result = ' '.join(fixed_sentences)
        
        # Ensure proper ending punctuation
        if result and not result.endswith(('.', '!', '?')):
            result += '.'
        
        return result
    
    def _improve_fluency(self, text: str) -> str:
        """Improve the fluency and coherence of the summary."""
        if not text:
            return text
            
        # Split into sentences for processing
        sentences = re.split(r'(?<=[.!?])\s+', text)
        improved_sentences = []
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Add transition words for better flow
            if i > 0 and len(improved_sentences) > 0:
                # Check if sentence needs a transition
                prev_sentence = improved_sentences[-1].lower()
                current_sentence = sentence.lower()
                
                # Add appropriate transitions
                if 'however' not in current_sentence and 'but' not in current_sentence:
                    if any(word in prev_sentence for word in ['increase', 'rise', 'grow', 'up']):
                        if any(word in current_sentence for word in ['decrease', 'fall', 'drop', 'down']):
                            sentence = "However, " + sentence.lower()
                    elif any(word in prev_sentence for word in ['said', 'stated', 'announced']):
                        if not any(word in current_sentence for word in ['additionally', 'furthermore', 'meanwhile']):
                            sentence = "Additionally, " + sentence.lower()
            
            # Fix common fluency issues
            sentence = re.sub(r'\b(The|A|An)\s+(The|A|An)\b', r'\1', sentence, flags=re.IGNORECASE)
            sentence = re.sub(r'\b(is|was|are|were)\s+(is|was|are|were)\b', r'\1', sentence, flags=re.IGNORECASE)
            
            # Ensure proper capitalization
            sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
            
            improved_sentences.append(sentence)
        
        # Join with proper spacing
        result = ' '.join(improved_sentences)
        
        # Final cleanup
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Ensure proper ending
        if result and not result.endswith(('.', '!', '?')):
            result += '.'
            
        return result
    

# Reddit Bot class
class RedditBot:
    def __init__(self):
        self.extractor = ContentExtractor()
        self.summarizer = SumySummarizer()
        self.news_extractor = GoogleNewsExtractor()
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
            
            # Extract content from the submission URL
            content = self.extractor.extract_content(submission.url)
            summary = None
            
            if content:
                logger.info(f"Extracted content of length: {len(content)} characters")
                summary = self.summarizer.generate_summary(content)
            
            # Get related news (excluding the original submission URL)
            related_news = self.news_extractor.get_related_news(submission.title, submission.url)
            
            # Post comment if we have summary or related news
            if summary or related_news:
                if summary:
                    logger.info(f"Generated summary: {summary[:60]}...")
                else:
                    logger.info("No content extracted, but found related news")
                    
                self._post_comment(submission, summary, related_news)
            else:
                logger.warning("Both summary generation and news extraction failed")
                
        except Exception as e:
            logger.error(f"Error processing submission {submission.id}: {e}", exc_info=True)

    def _post_comment(self, submission, summary: Optional[str], related_news: List[Dict[str, str]]):
        """Posts a comment on the submission with the generated summary and related news."""
        try:
            # Format the comment according to the specified template
            formatted_comment = self._format_comment(submission.title, summary, related_news)
            submission.reply(formatted_comment)
            logger.info(f"Comment posted successfully on submission {submission.id}")
            time.sleep(Config.COMMENT_DELAY)
        except Exception as e:
            logger.error(f"Failed to post comment on submission {submission.id}: {e}")

    def _format_comment(self, title: str, summary: Optional[str], related_news: List[Dict[str, str]]) -> str:
        """Format the comment according to the specified template."""
        
        # Build the comment parts
        comment_parts = []
        
        # Header
        comment_parts.append(f'📰 **Summary for:** "{title}"')
        comment_parts.append("")  # Empty line
        comment_parts.append("---")
        comment_parts.append("")
        
        # Summary section (if available)
        if summary:
            comment_parts.append("💡 **Summary:**")
            comment_parts.append("")
            comment_parts.append(f"> {summary}")
            comment_parts.append("")
            comment_parts.append("")
        else:
            comment_parts.append("💡 **Summary:**")
            comment_parts.append("")
            comment_parts.append("> No content could be extracted from the original link for summarization.")
            comment_parts.append("")
            comment_parts.append("")
        
        comment_parts.append("---")
        comment_parts.append("")
        
        # Related news section
        comment_parts.append("📰 **Related News:**")
        comment_parts.append("")
        
        if related_news:
            for news_item in related_news:
                comment_parts.append(f"🔗 [{news_item['title']}]({news_item['url']})")
                comment_parts.append("")
                comment_parts.append("")
        else:
            comment_parts.append("🔗 No related news sources found at this time.")
            comment_parts.append("")
            comment_parts.append("")
        
        comment_parts.append("---")
        comment_parts.append("")
        comment_parts.append("🛠️ **This is a bot for r/AfricaVoice!**")
        
        return '\n'.join(comment_parts)

# Run the bot
if __name__ == "__main__":
    bot = RedditBot()
    bot.run("AfricaVoice")