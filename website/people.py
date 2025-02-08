import os
from collections import Counter
from datetime import datetime, timedelta
from typing import List

import httpx

from nicegui import ui

# NOTE:
# requires a GitHub token with the necessary permissions read:org and read:user
# call with `GITHUB_TOKEN=ghp_XXX ./main.py`

URL = 'https://api.github.com/graphql'
HEADERS = {
    'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
    'Accept': 'application/vnd.github.v3+json',
}


def fetch_comments(*, days: int) -> List[str]:
    comments = []

    query = '''
        query($owner: String!, $repo: String!, $after: String) {
            repository(owner: $owner, name: $repo) {
                discussions(first: 50, orderBy: { field: UPDATED_AT, direction: DESC }, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        updatedAt
                        author { login }
                        comments(first: 100) {
                            nodes {
                                author { login }
                                createdAt
                                replies(first: 50) {
                                    nodes {
                                        createdAt
                                        author { login }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    '''
    cursor = None
    while True:
        variables = {'owner': 'zauberzeug', 'repo': 'nicegui', 'after': cursor}
        response = httpx.post(URL, json={'query': query, 'variables': variables}, headers=HEADERS, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            raise RuntimeError(f'GitHub API Error: {data["errors"]}')

        for discussion in data['data']['repository']['discussions']['nodes']:
            discussion_date = datetime.fromisoformat(discussion['updatedAt'].replace('Z', '+00:00'))
            if discussion_date < datetime.now(discussion_date.tzinfo) - timedelta(days=days):
                return comments

            for comment in discussion['comments']['nodes']:
                if not comment['author']:
                    continue
                if comment['author']['login'] == (discussion['author'] or {}).get('login'):
                    continue
                comment_date = datetime.fromisoformat(comment['createdAt'].replace('Z', '+00:00'))
                if comment_date < datetime.now(comment_date.tzinfo) - timedelta(days=days):
                    continue
                comments.append(comment['author']['login'])
                for reply in comment['replies']['nodes']:
                    if not reply['author']:
                        continue
                    if reply['author']['login'] == (discussion['author'] or {}).get('login'):
                        continue
                    comments.append(reply['author']['login'])

        if not data['data']['repository']['discussions']['pageInfo']['hasNextPage']:
            return comments
        cursor = data['data']['repository']['discussions']['pageInfo']['endCursor']


def fetch_pull_requests(*, days: int) -> List[str]:
    pull_requests = []

    query = '''
        query($owner: String!, $repo: String!, $after: String) {
            repository(owner: $owner, name: $repo) {
                pullRequests(first: 50, orderBy: { field: UPDATED_AT, direction: DESC }, after: $after) {
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                    nodes {
                        author { login }
                        updatedAt
                        merged
                    }
                }
            }
        }
    '''
    cursor = None
    while True:
        variables = {'owner': 'zauberzeug', 'repo': 'nicegui', 'after': cursor}
        response = httpx.post(URL, json={'query': query, 'variables': variables}, headers=HEADERS, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            raise RuntimeError(f'GitHub API Error: {data["errors"]}')

        for pr in data['data']['repository']['pullRequests']['nodes']:
            if not pr['author'] or not pr['merged']:
                continue
            pr_date = datetime.fromisoformat(pr['updatedAt'].replace('Z', '+00:00'))
            if pr_date < datetime.now(pr_date.tzinfo) - timedelta(days=days):
                return pull_requests
            pull_requests.append(pr['author']['login'])

        if not data['data']['repository']['pullRequests']['pageInfo']['hasNextPage']:
            return pull_requests
        cursor = data['data']['repository']['pullRequests']['pageInfo']['endCursor']


def show_people(days: int = 10) -> None:
    pull_requests = fetch_pull_requests(days=days)
    with ui.column(align_items='center').classes('mx-auto mt-8'):
        ui.label(f'Most merged pull requests in the last {days} days').classes('text-2xl')
        with ui.row().classes('justify-center'):
            for login, count in Counter(pull_requests).most_common():
                if login == 'dependabot':
                    continue
                with ui.link(target=f'https://github.com/{login}'):
                    with ui.column(align_items='center').classes('gap-1 min-w-24'):
                        ui.image(f'https://github.com/{login}.png').classes('w-12 h-12 rounded-full')
                        ui.label(login)
                        ui.label(f'{count} PRs' if count > 1 else '1 PR').classes('text-gray-500')

    comments = fetch_comments(days=days)
    with ui.column(align_items='center').classes('mx-auto mt-8'):
        ui.label(f'Most replies in discussions in the last {days} days').classes('text-2xl')
        with ui.row().classes('justify-center'):
            for login, count in Counter(comments).most_common():
                with ui.column(align_items='center').classes('gap-1 min-w-24'):
                    ui.image(f'https://github.com/{login}.png').classes('w-12 h-12 rounded-full')
                    ui.label(login)
                    ui.label(f'{count} replies' if count > 1 else '1 reply').classes('text-gray-500')
