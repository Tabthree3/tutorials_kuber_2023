#!/usr/bin/env python

import argparse
import os
import logging
from datetime import datetime

import yaml
from github import Auth, Github, GithubException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_repo_file(repo, file_path, message, content, branch, sha):
    """Update a file in the remote GitHub repository."""
    try:
        repo.update_file(file_path, message, content, sha, branch=branch)
        logging.info(f'Successfully updated "{file_path}" in branch "{branch}".')
    except GithubException as e:
        logging.error(f'Failed to update file "{file_path}": {e}')
        raise

def create_branch(repo, branch):
    """Create a new branch in the remote GitHub repository."""
    try:
        sb = repo.get_branch(repo.default_branch)
        repo.create_git_ref(ref=f'refs/heads/{branch}', sha=sb.commit.sha)
        logging.info(f'Successfully created branch "{branch}".')
    except GithubException as e:
        logging.error(f'Failed to create branch "{branch}": {e}')
        raise

def create_pr(repo, branch, title):
    """Create a Pull Request in the remote GitHub repository."""
    try:
        repo.create_pull(base=repo.default_branch, head=branch, title=title)
        logging.info(f'Successfully created Pull Request "{title}" from branch "{branch}".')
    except GithubException as e:
        logging.error(f'Failed to create Pull Request: {e}')
        raise

def get_repo(name):
    """Get GitHub repository by name."""
    try:
        github_token = os.environ['GITHUB_TOKEN']
        auth = Auth.Token(github_token)
        g = Github(auth=auth)
        return g.get_repo(name)
    except GithubException as e:
        logging.error(f'Failed to retrieve repository "{name}": {e}')
        raise

def modify_application(repo, env, service, branch, annotation_key=None):
    """Modify ArgoCD Application annotations to pause or resume."""
    file_path = f'envs/{env}/{service}/application.yaml'
    contents = repo.get_contents(file_path, ref=repo.default_branch)
    app = yaml.safe_load(contents.decoded_content.decode())

    if annotation_key:
        app['metadata']['annotations'][annotation_key] = '*'
    else:
        app['metadata']['annotations'].pop(annotation_key, None)

    app_yaml = yaml.dump(app, default_flow_style=False, explicit_start=True)
    update_repo_file(repo, contents.path, f'Modify {service} in {env}.', app_yaml, branch, contents.sha)

def handle_services(repo, env, services, branch, action):
    """Handle services for pause, resume, or push actions."""
    for svc in services:
        if action == 'pause':
            annotation_key = f'argocd-image-updater.argoproj.io/{svc.name}.ignore-tags'
            modify_application(repo, env, svc.name, branch, annotation_key)
        elif action == 'resume':
            annotation_key = f'argocd-image-updater.argoproj.io/{svc.name}.ignore-tags'
            modify_application(repo, env, svc.name, branch)

def options():
    """Add command-line arguments to the script."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-env', help='Source environment')
    parser.add_argument('--target-env', help='Target environment')
    parser.add_argument('--action', help='Action to perform (pause, resume, push)')
    return parser.parse_args()

def main():
    """Entrypoint to the GitOps script."""
    args = options()
    today = datetime.today().strftime('%Y-%m-%d')

    repository = get_repo('antonputra/k8s')
    branch_name = f'{args.action}-{args.target-env}-{today}'
    
    # Create branch and perform action
    create_branch(repository, branch_name)

    # Handle different actions
    if args.action == 'pause' or args.action == 'resume':
        services = repository.get_contents(f'envs/{args.target_env}')
        handle_services(repository, args.target_env, services, branch_name, args.action)
        create_pr(repository, branch_name, f'{args.action.capitalize()} the {args.target_env} environment.')
    elif args.action == 'push':
        logging.info('Push logic will be handled here (same as previous implementation).')
