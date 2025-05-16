import os
import re
import time
import praw
import argparse
import logging
import requests
import textwrap
import importlib
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime
from transformers import pipeline

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
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.text.strip() if soup.title else ""

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.extract()

        paragraphs = soup.find_all('p')
        text = ' '.join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])

        authors = []
        author_patterns = ['author', 'byline', 'writer']
        for pattern in author_patterns:
            for element in soup.find_all(class_=re.compile(pattern, re.I)):
                author_text = element.get_text().strip()
                if 10 < len(author_text) < 100:
                    authors.append(author_text)

        if not authors:
            meta_author = soup.find('meta', {'name': re.compile('author', re.I)})
            if meta_author and meta_author.get('content'):
                authors.append(meta_author.get('content').strip())

        publish_date = None
        try:
            time_element = soup.find(['time', 'span', 'div'], {'datetime': True})
            if time_element and time_element.get('datetime'):
                publish_date = datetime.fromisoformat(time_element['datetime'].replace('Z', '+00:00'))
        except:
            pass

        if not publish_date:
            for meta in soup.find_all('meta'):
                if meta.get('property') in ['article:published_time', 'og:published_time'] and meta.get('content'):
                    try:
                        publish_date = datetime.fromisoformat(meta['content'].replace('Z', '+00:00'))
                        break
                    except:
                        pass

        if len(text) < 100:
            logger.warning(f"Article text seems too short ({len(text)} chars). Extraction may have failed.")

        return {
            "title": title,
            "text": text,
            "authors": authors,
            "publish_date": publish_date,
            "top_image": None
        }
    except Exception as e:
        logger.error(f"Failed to extract article from {url}: {str(e)}")
        return None

def summarize_text(text, max_length=150, min_length=40):
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        chunks = textwrap.wrap(text, 1024)
        summaries = [summarizer(chunk, max_length=max_length, min_length=min_length, do_sample=False)[0]['summary_text']
                     for chunk in chunks if len(chunk) > 50]
        final_summary = " ".join(summaries)
        if len(final_summary) > 9500:
            final_summary = final_summary[:9500] + "..."
        return final_summary
    except Exception as e:
        logger.error(f"Failed to summarize text: {str(e)}")
        return "Error generating summary."

def format_reddit_comment(article_data, summary):
    comment = f"# {article_data['title']}\n\n"
    if article_data['authors']:
        comment += f"**Authors:** {', '.join(article_data['authors'])}\n\n"
    if article_data['publish_date']:
        comment += f"**Published:** {article_data['publish_date'].strftime('%Y-%m-%d')}\n\n"
    comment += "## Summary\n\n"
    comment += summary + "\n\n"
    comment += "---\n*This summary was automatically generated. I am a bot.*"
    return comment

def process_new_submissions(subreddit_name, processed_ids_file="processed_ids.txt"):
    processed_ids = set()
    if os.path.exists(processed_ids_file):
        with open(processed_ids_file, "r") as f:
            processed_ids = set(line.strip() for line in f)

    reddit = setup_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    logger.info(f"Monitoring subreddit r/{subreddit_name} for new submissions...")

    for submission in subreddit.stream.submissions(skip_existing=True):
        if submission.id in processed_ids or submission.is_self:
            processed_ids.add(submission.id)
            continue

        url = submission.url
        if any(domain in url for domain in ['.com/', '.org/', '.net/', '.gov/', '.edu/']):
            logger.info(f"Processing new submission: {submission.title} - {url}")
            article_data = extract_article_content(url)
            if not article_data or not article_data['text']:
                logger.warning(f"Could not extract article content from {url}")
                processed_ids.add(submission.id)
                continue

            summary = summarize_text(article_data['text'])
            comment_text = format_reddit_comment(article_data, summary)
            try:
                submission.reply(comment_text)
                logger.info(f"Posted summary comment to: {submission.title}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Failed to post comment: {str(e)}")

            processed_ids.add(submission.id)
            with open(processed_ids_file, "a") as f:
                f.write(f"{submission.id}\n")

def get_subreddits():
    try:
        try:
            subreddits_module = importlib.import_module('subreddits')
            return subreddits_module.SUBREDDITS
        except ImportError:
            logger.error("subreddits.py file not found. Creating example file.")
            with open('subreddits.py', 'w') as f:
                f.write('# List of subreddits to monitor\n')
                f.write('SUBREDDITS = [\n')
                f.write('    "news",\n')
                f.write('    "worldnews",\n')
                f.write('    "politics",\n')
                f.write(']\n')
            importlib.invalidate_caches()
            subreddits_module = importlib.import_module('subreddits')
            return subreddits_module.SUBREDDITS
    except Exception as e:
        logger.error(f"Error loading subreddits: {str(e)}")
        return ["news"]

def main():
    parser = argparse.ArgumentParser(description='Reddit News Article Summarizer')
    parser.add_argument('--subreddit', '-s', type=str, help='Subreddit name (without the r/). Overrides subreddits.py')
    parser.add_argument('--monitor', '-m', action='store_true', help='Monitor for new submissions continuously')
    parser.add_argument('--all', '-a', action='store_true', help='Monitor all subreddits listed in subreddits.py')

    args = parser.parse_args()

    if args.subreddit:
        subreddits_to_monitor = [args.subreddit]
    elif args.all:
        subreddits_to_monitor = get_subreddits()
    else:
        all_subreddits = get_subreddits()
        subreddits_to_monitor = [all_subreddits[0]] if all_subreddits else ["news"]

    if args.monitor:
        logger.info(f"Starting continuous monitoring of: {', '.join(['r/' + sub for sub in subreddits_to_monitor])}")
        try:
            multireddit = '+'.join(subreddits_to_monitor)
            process_new_submissions(multireddit)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Exiting...")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
    else:
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

if __name__ == "__main__":
    main()