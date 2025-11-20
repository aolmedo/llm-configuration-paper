import os
import csv
from dotenv import load_dotenv
from github import Github
from github import Auth


load_dotenv()


def get_repos(query=None):
    API_TOKEN = os.getenv("GITHUB_API_TOKEN")
    auth = Auth.Token(API_TOKEN)

    g = Github(auth=auth)

    api_result = g.search_repositories(query=query)

    repositories = []

    for repo in api_result:
        topics = ','.join(repo.topics)
        info = [repo.id, repo.name, repo.description, repo.git_url, topics]
        repositories.append(info)
       
    return repositories


def filter_repos(all_repos):
    filtered_repos = []
    interested_topics = ['ai', 'chatgpt', 'dall-e', 'generative-ai', 'generativeai', 'gpt',
                         'llm', 'chatbot', 'transformers', 'language-model', 'chatbots',
                         'llms', 'agent', 'gemini', 'llama', 'app', 'ui', 'claude',
                         'artificial-intelligence', 'large-language-models', 'lora',
                         'mistral', 'langchain', 'assistant', 'ollama', 'agents', 'bert']
    excluded_words = ['scratch', 'papers', 'paper', 'colab', 'education', 'course',
                      'tutorial', 'guide', 'example', 'lessons', 'list', 'sample',
                      'notebook', 'deprecated', 'abandoned', 'demo']

    for repo in all_repos:
        to_insert = True
        topics = set(repo[4].split(','))
        for word in excluded_words:
            to_insert = to_insert and ((repo[1] and not word in repo[1].lower()) and (repo[2] and not word in repo[2].lower()))
        z = topics.intersection(set(interested_topics))
        if len(z) >= 3 and to_insert:
            filtered_repos.append(repo)
    return filtered_repos


gpt_repos = get_repos(query='topic:gpt language:Python stars:>100')
llm_repos = get_repos(query='topic:llm language:Python stars:>100')
chatbot_repos = get_repos(query='topic:chatbot language:Python stars:>100')

selected_repos = filter_repos(gpt_repos + llm_repos + chatbot_repos)


with open('selected_repos.csv', 'w') as a_file:
    writer = csv.writer(a_file, delimiter=';')
    for repository in selected_repos:
        writer.writerow(repository)

