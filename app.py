import praw
import requests
import newspaper
from newspaper import Article
import textwrap
import os
import time
import argparse
from dotenv import load_dotenv
import logging
from transformers import pipeline
import importlib

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("summarizer.log"), logging.StreamHandler()]
)
logger = logging.getLogger("Reddit News Summarizer")

# Load environment variables from .env file
load_dotenv()

def setup_reddit_client():
    """Setup and return Reddit API client using credentials."""
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
            user_agent=os.getenv("REDDIT_USER_AGENT", "NewsArticleSummarizer v1.0")
        )
        logger.info(f"Authenticated as {reddit.user.me()}")
        return reddit
    except Exception as e:
        logger.error(f"Failed to authenticate with Reddit: {str(e)}")
        raise

def extract_article_content(url):
    """Extract article content from a URL using newspaper3k."""
    try:
        article = Article(url)
        article.download()
        article.parse()
        
        # If article text is too short, it might not be properly extracted
        if len(article.text) < 100:
            logger.warning(f"Article text seems too short ({len(article.text)} chars). Extraction may have failed.")
        
        return {
            "title": article.title,
            "text": article.text,
            "authors": article.authors,
            "publish_date": article.publish_date,
            "top_image": article.top_image
        }
    except Exception as e:
        logger.error(f"Failed to extract article from {url}: {str(e)}")
        return None

def summarize_text(text, max_length=150, min_length=40):
    """Summarize text using Hugging Face transformers."""
    try:
        # Initialize the summarization pipeline
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        
        # Split into chunks if text is too long
        max_chunk_size = 1024  # Maximum size for BART model
        chunks = textwrap.wrap(text, max_chunk_size)
        summaries = []
        
        for chunk in chunks:
            if len(chunk) < 50:  # Skip very small chunks
                continue
                
            summary = summarizer(chunk, max_length=max_length, min_length=min_length, do_sample=False)
            if summary and len(summary) > 0:
                summaries.append(summary[0]['summary_text'])
        
        # Combine summaries if multiple chunks
        final_summary = " ".join(summaries)
        
        # Ensure our combined summary isn't too long for a Reddit comment
        if len(final_summary) > 9500:  # Reddit comment limit is around 10,000 characters
            final_summary = final_summary[:9500] + "..."
            
        return final_summary
    except Exception as e:
        logger.error(f"Failed to summarize text: {str(e)}")
        return "Error generating summary."

def format_reddit_comment(article_data, summary):
    """Format the summary as a Reddit comment."""
    comment = f"# {article_data['title']}\n\n"
    
    if article_data['authors']:
        comment += f"**Authors:** {', '.join(article_data['authors'])}\n\n"
    
    if article_data['publish_date']:
        comment += f"**Published:** {article_data['publish_date'].strftime('%Y-%m-%d')}\n\n"
    
    comment += "## Summary\n\n"
    comment += summary + "\n\n"
    comment += "---\n"
    comment += "*This summary was automatically generated. I am a bot.*"
    
    return comment

def process_new_submissions(subreddit_name, processed_ids_file="processed_ids.txt"):
    """Process only new submissions from a subreddit and post summaries."""
    # Load previously processed submission IDs
    processed_ids = set()
    if os.path.exists(processed_ids_file):
        with open(processed_ids_file, "r") as f:
            processed_ids = set(line.strip() for line in f)
    
    reddit = setup_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    
    logger.info(f"Monitoring subreddit r/{subreddit_name} for new submissions...")
    
    # Use the stream method to get real-time new submissions
    for submission in subreddit.stream.submissions(skip_existing=True):
        # Skip if already processed (redundant with skip_existing but kept as safety)
        if submission.id in processed_ids:
            continue
        
        # Skip self posts (text posts)
        if submission.is_self:
            logger.info(f"Skipping self post: {submission.title}")
            processed_ids.add(submission.id)
            continue
        
        url = submission.url
        
        # Check if URL is likely a news article
        if any(domain in url for domain in ['.com/', '.org/', '.net/', '.gov/', '.edu/']):
            logger.info(f"Processing new submission: {submission.title} - {url}")
            
            # Extract article content
            article_data = extract_article_content(url)
            if not article_data or not article_data['text']:
                logger.warning(f"Could not extract article content from {url}")
                processed_ids.add(submission.id)
                continue
            
            # Summarize the article
            summary = summarize_text(article_data['text'])
            
            # Format and post a comment
            comment_text = format_reddit_comment(article_data, summary)
            try:
                submission.reply(comment_text)
                logger.info(f"Posted summary comment to: {submission.title}")
                
                # Add a 5-second delay to avoid rate limiting
                time.sleep(5)
            except Exception as e:
                logger.error(f"Failed to post comment: {str(e)}")
            
        # Mark as processed
        processed_ids.add(submission.id)
        
        # Save processed ID immediately to avoid missing any if the script is interrupted
        with open(processed_ids_file, "a") as f:
            f.write(f"{submission.id}\n")

def get_subreddits():
    """Load subreddits from subreddits.py file."""
    try:
        # Try to import the subreddits module
        try:
            subreddits_module = importlib.import_module('subreddits')
            return subreddits_module.SUBREDDITS
        except ImportError:
            logger.error("subreddits.py file not found. Creating example file.")
            # Create a default subreddits.py file if it doesn't exist
            with open('subreddits.py', 'w') as f:
                f.write('# List of subreddits to monitor\n')
                f.write('# Add or remove subreddit names as needed\n')
                f.write('SUBREDDITS = [\n')
                f.write('    "",\n')
                f.write('    "",\n')
                f.write('    "",\n')
                f.write(']\n')
            # Try importing again
            importlib.invalidate_caches()
            subreddits_module = importlib.import_module('subreddits')
            return subreddits_module.SUBREDDITS
    except Exception as e:
        logger.error(f"Error loading subreddits: {str(e)}")
        return ["news"]  # Default to r/news if everything fails

def main():
    """Main function to parse arguments and run the summarizer."""
    parser = argparse.ArgumentParser(description='Reddit News Article Summarizer')
    parser.add_argument('--subreddit', '-s', type=str, 
                        help='Subreddit name (without the r/). Overrides subreddits.py')
    parser.add_argument('--monitor', '-m', action='store_true',
                        help='Monitor for new submissions continuously')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Monitor all subreddits listed in subreddits.py')
    
    args = parser.parse_args()
    
    # Determine which subreddits to monitor
    if args.subreddit:
        # If specific subreddit is provided via command line, use that
        subreddits_to_monitor = [args.subreddit]
    elif args.all:
        # If --all flag is provided, use all subreddits from the file
        subreddits_to_monitor = get_subreddits()
    else:
        # By default, use the first subreddit from the file
        all_subreddits = get_subreddits()
        subreddits_to_monitor = [all_subreddits[0]] if all_subreddits else ["news"]

    if args.monitor:
        logger.info(f"Starting continuous monitoring of: {', '.join(['r/' + sub for sub in subreddits_to_monitor])}")
        try:
            # If monitoring multiple subreddits, create a multi-reddit
            if len(subreddits_to_monitor) > 1:
                multireddit = '+'.join(subreddits_to_monitor)
                process_new_submissions(multireddit)
            else:
                process_new_submissions(subreddits_to_monitor[0])
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Exiting...")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
    else:
        # One-time check mode
        reddit = setup_reddit_client()
        
        for subreddit_name in subreddits_to_monitor:
            logger.info(f"Running one-time check for r/{subreddit_name}...")
            subreddit = reddit.subreddit(subreddit_name)
            latest = list(subreddit.new(limit=1))
            
            if latest:
                submission = latest[0]
                if not submission.is_self and any(domain in submission.url for domain in ['.com/', '.org/', '.net/', '.gov/', '.edu/']):
                    logger.info(f"Processing: {submission.title} - {submission.url}")
                    
                    article_data = extract_article_content(submission.url)
                    if article_data and article_data['text']:
                        summary = summarize_text(article_data['text'])
                        comment_text = format_reddit_comment(article_data, summary)
                        try:
                            submission.reply(comment_text)
                            logger.info(f"Posted summary comment to: {submission.title}")
                        except Exception as e:
                            logger.error(f"Failed to post comment: {str(e)}")
            
        logger.info("Finished one-time run.")

if __name__ == "__main__":
    main()