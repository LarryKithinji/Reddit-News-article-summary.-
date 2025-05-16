import praw
from prawcore.exceptions import RequestException
import smrzr
from altsummary import summary
import os
import find_other_news_sources
import itertools
from prawoauth2 import PrawOAuth2Mini
import blacklist
from time import sleep
import subreddits
from newspaper import Article
import message_templates as mt


def init():
    r = praw.Reddit(
        client_id=os.environ['app_key'],
        client_secret=os.environ['app_secret'],
        refresh_token=os.environ['refresh_token'],
        user_agent="Samachar Bot for /r/india by /u/sallurocks"
    )
    subreddit = r.subreddit("+".join(subreddits.subreddits))
    return r, subreddit


def post_tracker():
    fo = open("looked.txt", "a+")
    fo.seek(0)
    str1 = fo.read()
    fo.seek(0, 2)
    return fo, str1


def add_submission(file_handler, submission):
    file_handler.write(submission.id + " ")


def is_posted(comments):
    return any(str(comment.author) == 'samacharbot2' for comment in comments)


def summarize_smrzr(url):
    summ_article = smrzr.Summarizer(url, 4, 'default', 'newspaper')
    keypoints = summ_article.keypoints
    summ = summ_article.summary
    message = "\n\n> * " + "\n\n> * ".join(keypoints)
    message = message.replace("`", "").replace("#", "\\#")
    return summ, message, summ_article.text


def summarize_other(url):
    article = Article(url)
    article.download()
    article.parse()
    text = article.text
    keypoints = summary(text)
    summ = article.title
    keypoints = keypoints.replace("`", "").replace("#", "\\#")
    return summ, keypoints, text


def final_checks(text):
    if "Never miss a great news story!" in text:
        print("check failed")
        return False
    return True


def post_comment(submission, comment):
    try:
        submission.reply(comment)
    except Exception as e:
        print("Error posting comment\n", type(e), e.args, e, submission.id)


def get_relevant(link):
    relevant_list = find_other_news_sources.find_other_news_sources(url=link)
    relevant_message = mt.relevant_message
    if not relevant_list:
        return relevant_message

    seen_links = set()
    for title, url in zip(*zip(*relevant_list)):
        if url == link or url in seen_links:
            continue
        title = title or "This"
        relevant_message += f"\n\n> * [{title}]({url})"
        seen_links.add(url)
    return relevant_message


def process_summarization(file_handler, submission, method):
    if method == 'smrzr':
        add_submission(file_handler, submission)

    if is_posted(submission.comments):
        print("already posted")
        return

    try:
        if method == 'smrzr':
            summ, keypoints, article_text = summarize_smrzr(submission.url)
            print(f"Finished {submission.id} with smrzr")
        elif method == 'other':
            summ, keypoints, article_text = summarize_other(submission.url)
            print(f"Finished {submission.id} with other")
        else:
            return
    except Exception as e:
        print(f"Summarization error: {e}")
        return

    if len(keypoints) < 150:
        return

    relevant_message = get_relevant(submission.url)

    if final_checks(article_text):
        new_comment = summ + mt.br + keypoints + mt.br + relevant_message + mt.br + mt.endmsg
        post_comment(submission, new_comment)


def check_delete(r):
    for msg in r.inbox.unread(limit=None):
        if msg.body.lower() == 'delete':
            try:
                comment = r.comment(msg.id)
                parent = r.comment(comment.parent_id.split('_')[1])
                author = r.submission(parent.link_id.split('_')[1]).author
                if str(msg.author.name) == str(author):
                    parent.delete()
                msg.mark_read()
            except Exception as e:
                print("Error in delete", type(e), e.args, e)
                msg.mark_read()


def check_conditions(submission, ids):
    return not submission.is_self and submission.domain not in blacklist.blocked and submission.id not in ids


def start():
    r, subreddit = init()
    while True:
        try:
            submissions = subreddit.new(limit=50)
        except RequestException:
            print("HTTP Exception")
            sleep(300)
            continue

        nothing = True
        for submission in submissions:
            print(f"Working on - {submission.id}")
            fo, ids = post_tracker()

            if submission.score >= 0 and check_conditions(submission, ids):
                nothing = False
                try:
                    process_summarization(fo, submission, 'smrzr')
                except smrzr.ArticleExtractionFail:
                    print("Article Extraction Failed")
                except AssertionError:
                    print("Assertion Error")
                    process_summarization(fo, submission, 'other')
                except Exception as e:
                    print("Unknown ERROR", type(e), e.args, e, submission.id)
                finally:
                    fo.close()
            else:
                print("Nothing to do, checking messages")
                check_delete(r)

        if nothing:
            print("Nothing to do, sleeping for 1 minute")
            sleep(60)


if __name__ == '__main__':
    start()