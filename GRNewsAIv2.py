# Project Homepage: https://github.com/alexandros-koutsioumpas/GRNewsAIv2/
# Previous Release: https://github.com/alexandros-koutsioumpas/GRNewsAI/
# Installation procedure
# You will need Python > 3.9 installed
# pip install -r requirements.txt
# Sometimes Python Install Certificates script needs to be executed
# Install Ollama if you have not done already
# then pull llama KriKri LLM (ollama pull ilsp/llama-krikri-8b-instruct:latest)
# then pull gemma3 LLM (ollama pull gemma3:4b)
# 
# Alternatively to Ollama you may
# Install LMStudio (local or remote) if you have not done already
# and set up llama KriKri and Gemma3:4b for LMStudio
# If you run a local LMStudio HTTP API, set LMSTUDIO_API_URL environment variable
# Example: setx LMSTUDIO_API_URL "http://127.0.0.1:8080/v1/chat/completions"
# then run the script

__author__ = "Alexandros Koutsioumpas"
__credits__ = "T. Kleisas (initial LMStudio compatibility), Y. Mertzanis (grouping progress bar, LMStudio bug cleaning)"
__license__ = "MIT"
__date__ = "2025/12/20"
__status__ = "v2.0"

# Change Log
# versiom 0.1: first release
# version 0.2: LMStudio support and improved Windows compatibility (many thanks to T. Kleisas "https://github.com/tkleisas")
# version 2.0: Many updates. Now the script identifies the most covered news in the defined sources and creates a coherent summary in md,pdf,html and mp3


# === CONFIGURABLE SETTINGS ===
ENGINE = 'ollama'  # "ollama" or "LMStudio"

# Auto-select models based on ENGINE
if ENGINE == 'ollama':
    CLASSIFICATION_MODEL = 'gemma3:4b'
    BROADCAST_MODEL = 'ilsp/llama-krikri-8b-instruct:latest'
elif ENGINE == 'LMStudio':
    CLASSIFICATION_MODEL = 'google/gemma-3-4b'
    BROADCAST_MODEL = 'llama-krikri-8b-instruct'

TTS_VOICE = "el-GR-NestorasNeural"  # Change to "el-GR-AthinaNeural" for female voice
NUM_ARTICLES = 25  # Number of max articles to fetch from each RSS source
NUM_STORIES = 7  # Number of stories to include in the final output
# ===========================

import os
import yaml
import feedparser
from newspaper import Article
from newspaper import Config
from datetime import datetime
import asyncio
import edge_tts
import ollama
from tqdm import tqdm 
from markdown_pdf import MarkdownPdf, Section
import markdown
from googlenewsdecoder import gnewsdecoder
import requests
import json
from datetime import datetime
import sys
import time

# Small LMStudio REST client helper. Uses LMSTUDIO_API_URL env var or
# defaults to http://127.0.0.1:8080/v1/chat/completions which is a common
# LMStudio-compatible endpoint shape.
_LMSTUDIO_API_URL = os.environ.get('LMSTUDIO_API_URL', 'http://127.0.0.1:1234/v1/chat/completions')


def LMStudio_chat(model, messages, timeout=600):
    """Send chat request to LMStudio-compatible HTTP API and normalize response.
    Returns a dict with shape {'message': {'content': '<text>'}} to match the
    original ollama.chat usage in this script.
    """
    payload = {
        'model': model,
        'messages': messages,
    }
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(_LMSTUDIO_API_URL, headers=headers, data=json.dumps(payload), timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    # Common response shapes: OpenAI-like -> {'choices': [{'message': {'content': '...'}}]}
    if isinstance(data, dict):
        choices = data.get('choices')
        if choices and isinstance(choices, list):
            first = choices[0]
            msg = first.get('message') or {'content': first.get('text')}
            content = msg.get('content') if isinstance(msg, dict) else str(msg)
            return {'message': {'content': content}}
        if 'message' in data and isinstance(data['message'], dict) and 'content' in data['message']:
            return {'message': {'content': data['message']['content']}}
        # fallback: stringify body
        return {'message': {'content': json.dumps(data, ensure_ascii=False)}}
    return {'message': {'content': str(data)}}

# Load feed URLs from YAML configuration
def load_feeds(config_path='feeds_gr.yaml'):
    """Load feeds from YAML with robust encoding handling.
    Tries utf-8, then utf-8-sig, then latin-1 to avoid platform-specific
    decoding errors (Windows cp1253 issues). Returns an empty list if the
    file is missing or the YAML has no 'feeds' key.
    """
    encodings = ['utf-8', 'utf-8-sig', 'latin-1']
    last_exc = None
    for enc in encodings:
        try:
            with open(config_path, 'r', encoding=enc) as file:
                config = yaml.safe_load(file)
            if config is None:
                return []
            return config.get('feeds', [])
        except FileNotFoundError:
            # If the file doesn't exist, return empty list so caller can handle it
            return []
        except UnicodeDecodeError as e:
            last_exc = e
            # try next encoding
            continue
        except Exception as e:
            # propagate other YAML parsing errors with context
            raise RuntimeError(f"Error loading feeds from {config_path}: {e}") from e
    # If we exhausted encodings, raise a clear error including the last decode exception
    raise UnicodeDecodeError(last_exc.encoding if hasattr(last_exc, 'encoding') else 'unknown',
                             b'', 0, 1,
                             f"Failed to decode {config_path} with encodings {encodings}: {last_exc}")

# Fetch and parse articles from RSS feeds
def fetch_articles(feed_urls, max_articles):
    articles = []
    print("Ανάκτηση και κατέβασμα άρθρων από πηγές RSS...\n")
    for url in tqdm(feed_urls, desc="Ανάκτηση πηγών", unit="πηγές"):
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_articles]:
            articles.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', 'N/A')
            })
    return articles


def similarity_check(summaries, model=CLASSIFICATION_MODEL):
    match = 0
    scores = {}
    similarity_group = []
    for item in summaries:
        if len(item['title'].split()) > 5:
            similarity_group.append([item['title']])

    # Calculate initial estimate of total comparisons: n*(n-1)/2 unique pairs
    n = len(similarity_group)
    estimated_total = n * (n - 1) // 2

    pbar = tqdm(total=estimated_total, desc="Ομαδοποίηση άρθρων (~εκτίμηση)", unit="συγκρίσεις")

    outer_pass = True
    while outer_pass == True:
        inner_pass = True
        for i in range(len(similarity_group)):
            if i == len(similarity_group)-1:
                outer_pass = False
                break
            if inner_pass == False: break
            for j in range(len(similarity_group)):
                if inner_pass == False: break
                if i != j:
                    if similarity_group[i][0]+similarity_group[j][0] not in scores and similarity_group[j][0]+similarity_group[i][0] not in scores:
                        prompt = (
                            "Βαθμολόγησε από το 0 ως το 9 την ομοιότητα των δυο παρακάτω τίτλων. "
                            "Τίτλος 1: "+similarity_group[i][0]+", Τίτλος 2: "+similarity_group[j][0]+"\n"
                            "Απάντησε μόνο με το βαθμό.\n\n Βαθμός:"
                        )
                        if ENGINE == 'ollama':
                            response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}]) #, options = {"num_ctx": 2048})
                        if ENGINE == 'LMStudio':
                            response = LMStudio_chat(model=model, messages=[{"role": "user", "content": prompt}])
                        grade = response['message']['content'][0]
                        scores[similarity_group[i][0]+similarity_group[j][0]] = grade
                        pbar.update(1)
                        if grade == '9' or grade == 'Βαθμός: 9':
                            similarity_group[i].append(similarity_group[j][0])
                            similarity_group.remove(similarity_group[j])
                            inner_pass = False
                            match = match + 1

    pbar.close()


    similarity_group.sort(key=len)
    most_found = []
    for i in range(NUM_STORIES):
        if len(similarity_group[-i-1]) >= 2:
            for j in range(len(similarity_group[-i-1])):
                for item in summaries:
                    if item['title'] == similarity_group[-i-1][j]:
                        link = item['link']
                most_found.append({
                    'group' : i,
                    'title' : similarity_group[-i-1][j],
                    'link' : link
                    })
            

    return most_found


# Use Ollama or LMStudio to generate a cohesive news broadcast from all summaries
def generate_broadcast_new(grouped_articles, model=BROADCAST_MODEL):
    total = ''
    gen_titles = []
    gen_texts = []
    gen_links = []
    if len(grouped_articles) - 2 < NUM_STORIES:
        real_num_stories = len(grouped_articles) - 2
    else:
        real_num_stories = NUM_STORIES

    for i in range(real_num_stories):
        text = ''
        links = []
        for j in range(len(grouped_articles)):
            if grouped_articles[j]['group'] == i:
                try:
                    if "news.google.com" in grouped_articles[j]['link']:
                        interval_time = 1  # interval is optional, default is None
                        source_url = grouped_articles[j]['link']
                        #print('downloading: '+source_url)
                        try:
                            decoded_url = gnewsdecoder(source_url, interval=interval_time)

                            if decoded_url.get("status"):
                                #print("Decoded URL:", decoded_url["decoded_url"])
                                grouped_articles[j]['group'] = decoded_url["decoded_url"]
                            else:
                                print("Error:", decoded_url["message"])
                                grouped_articles[j]['group'] = ""
                        except Exception as e:
                            print(f"Error occurred: {e}")
                            grouped_articles[j]['group'] = ""
                    user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
                    config = Config()
                    config.browser_user_agent = user_agent
                    news_article = Article(grouped_articles[j]['link'], config=config)
                    news_article.download()
                    news_article.parse()
                    news_text = news_article.text #[:2000]
                    text = text + 'Τίτλος: ' + grouped_articles[j]['title'] + '\n' + news_text + '\n'
                    links.append(grouped_articles[j]['link'])
                    #print(summary)
                except Exception as e:
                    print(f"Error processing article: {grouped_articles[j]['link']}\n{e}")

                #text = text + 'Τίτλος: ' + grouped_articles[j]['title'] + '\n' + news_text + '\n'

        prompt = (
            "Με βάση τα ακόλουθα άρθρα, δημιούργησε μια περίληψη 2-3 παραγράφων διατηρώντας ενημερωτικό και ουδέτερο χαρακτήρα.:\n\n"
            f"{text}\n\nΠερίληψη:"
        )
        #print("Αριθμός λέξεων στο prompt: ", len(prompt.split()), ".")
        if ENGINE == 'ollama':
            response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}], options = {"num_ctx": 40960})
        if ENGINE == 'LMStudio':
            response = LMStudio_chat(model=model, messages=[{"role": "user", "content": prompt}])

        prompt = (
            "Δώσε μου ένα σύντομο τίτλο για το ακόλουθο κείμενο. Η απάντηση να περιέχει μόνο τον τίτλο.\n\n Κείμενο:"
            f"{response['message']['content']}.\n"
        )

        #print("Αριθμός λέξεων στο prompt: ", len(prompt.split()), ".")
        if ENGINE == 'ollama':
            response_title = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}], options = {"num_ctx": 40960})
        if ENGINE == 'LMStudio':
            response_title = LMStudio_chat(model=model, messages=[{"role": "user", "content": prompt}])

        total = total + response_title['message']['content'] + '\n\n' + response['message']['content'] + '\n --- \n'
        gen_titles.append(response_title['message']['content'])
        gen_texts.append(response['message']['content'])
        gen_links.append(links)
        print('.')

    return gen_titles,gen_texts,gen_links

# Save full broadcast with timestamped filename
def save_digest(digest_text, output_dir='.'):
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = os.path.join(output_dir, f'GR_digest_{timestamp}.md')
    with open(filename, 'w') as file:
        file.write(digest_text)
    try:
        #pdf = MarkdownPdf(toc_level=4, optimize=True)
        pdf = MarkdownPdf(optimize=True)
        pdf.add_section(Section(open(filename, encoding='utf-8').read()))
        pdf.meta["title"] = "News Bulletin"
        pdf.save(filename[:-3]+'.pdf')
    except:
        print('Πρόβλημα με την παραγωγή του PDF..')


    try:
        tempHtml = markdown.markdown(digest_text)
        with open(filename[:-3]+'.html', 'w') as f:
            realHtml = "<!DOCTYPE html>"
            realHtml += "<html>\n\n"
            realHtml += "<head>\n"
            realHtml += "<meta charset=\"UTF-8\">\n"
            realHtml +=  "<title>GRNewsAI_v2</title>\n"
            realHtml += "</head>\n\n"
            realHtml += "<body>\n"
            realHtml += tempHtml+"\n<body>\n\n"
            realHtml += "</html>"
            
            f.write(realHtml)
    except:
        print('Πρόβλημα με την παραγωγή του HTML..')
    return filename  # return path for TTS to use

# Convert broadcast to speech with timestamped filename
async def text_to_speech(text, output_path, voice=TTS_VOICE):
    communicate = edge_tts.Communicate(text.replace('*', ' ').replace('&', ' και ').replace(':', '.'), voice=voice)
    await communicate.save(output_path)

# Main workflow
def main():
    if ENGINE != 'ollama' and ENGINE != 'LMStudio':
        print('Ορίστε σωστά το LLM ENGINE, ollama ή LMStudio.')
        exit()
    print('Έναρξη εκτέλεσης script: '+datetime.today().strftime('%Y-%m-%d %H:%M:%S'))
    feed_urls = load_feeds()
    articles = fetch_articles(feed_urls, max_articles=NUM_ARTICLES)
    print("Αριθμός άρθρων : "+str(len(articles)))
    most_covered = similarity_check(articles)


    print('Παραγωγή σύνοψης ειδήσεων...')
    titles, texts, links = generate_broadcast_new(most_covered)
    broadcastnolinks='Ακολουθούν τα νέα με την ευρύτερη κάλυψη στις πηγές RSS που επιλέχθηκαν. \n \n'
    broadcast = 'GRNewsAI v2: '+datetime.today().strftime('%Y-%m-%d %H:%M') + '\n \n'
    broadcast +='Ακολουθούν τα νέα με την ευρύτερη κάλυψη στις πηγές RSS που επιλέχθηκαν. \n \n'
    for i in range(len(titles)):
        broadcast += '# ' + titles[i] + '\n' + texts[i] + '\n \n'
        broadcastnolinks += '# ' + titles[i] + '\n' + texts[i] + '\n \n'
        for j in range(len(links[i])):
            broadcast += '['+str(j+1)+']('+links[i][j]+') '
        broadcast += '\n' + '--- \n \n'
    broadcastnolinks += 'Τέλος δελτίου.'



    # Save digest and get timestamped filename
    digest_path = save_digest(broadcast)

    # Create matching timestamped mp3 path
    mp3_path = digest_path.replace('.md', '.mp3')
    asyncio.run(text_to_speech(broadcastnolinks, output_path=mp3_path))
    print('Λήξη εκτέλεσης script: '+datetime.today().strftime('%Y-%m-%d %H:%M:%S'))

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print('Μια εκτέλεση του script...')
        main()
    if len(sys.argv) == 2:
        if int(sys.argv[1]) > 0:
            print('Εκτέλεση κάθε '+ str(int(sys.argv[1])) +' ώρες..')
            while True:
                main()
                time.sleep(int(3600*int(sys.argv[1])))
        else:
            print('Σφάλμα στην εξωτερική παράμετρο...')

    if len(sys.argv) > 2:
        print('Δώστε μόνο μια εξωτερική παράμετρο...')
