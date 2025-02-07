#!/usr/bin/env python3
import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List

import httpx

# NOTE:
# requires a GitHub token with the necessary permissions read:org and read:user
# call with `GITHUB_TOKEN=ghp_XXX ./fetch_people.py`


def fetch_comments(*, days: int) -> List[Dict]:
    comments = []

    cursor = None
    while True:
        response = httpx.post(
            'https://api.github.com/graphql',
            json={
                'query': '''
                    query($owner: String!, $repo: String!, $after: String) {
                        repository(owner: $owner, name: $repo) {
                            discussions(first: 50, orderBy: { field: UPDATED_AT, direction: DESC }, after: $after) {
                                pageInfo {
                                    hasNextPage
                                    endCursor
                                }
                                nodes {
                                    updatedAt
                                    author {
                                        login
                                    }
                                    comments(first: 100) {
                                        nodes {
                                            author {
                                                login
                                            }
                                            createdAt
                                        }
                                    }
                                }
                            }
                        }
                    }
                ''',
                'variables': {
                    'owner': 'zauberzeug',
                    'repo': 'nicegui',
                    'after': cursor,
                },
            },
            headers={
                'Authorization': f'token {os.getenv("GITHUB_TOKEN")}',
                'Accept': 'application/vnd.github.v3+json',
            },
            timeout=10.0,
        )
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
                comments.append({
                    'login': comment['author']['login'],
                })

        if not data['data']['repository']['discussions']['pageInfo']['hasNextPage']:
            return comments
        cursor = data['data']['repository']['discussions']['pageInfo']['endCursor']


def main() -> None:
    comments = fetch_comments(days=30)
    counter = Counter(comment['login'] for comment in comments)
    for login, count in counter.most_common():
        if count >= 2:
            print(f'{login}: {count}')


if __name__ == '__main__':
    main()
