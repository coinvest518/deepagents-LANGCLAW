---
name: github
description: >
  Full GitHub control via Composio — 200 actions. Issues, PRs, commits, repos,
  branches, releases, webhooks, Actions workflows, collaborators, secrets,
  GitHub Pages, Gists, organizations, teams, code scanning, Codespaces, projects.
  Pre-authenticated. Trigger phrases: "github", "repo", "issue", "pull request",
  "PR", "commit", "branch", "release", "workflow", "merge".
license: MIT
compatibility: deepagents-cli
---

# GitHub Skill — 200 Actions

Call any action with `composio_action`. Account ID is in `COMPOSIO_GITHUB_ACCOUNT_ID`.

```
composio_action(
  action="GITHUB_<ACTION>",
  params={...},
  connected_account_id=COMPOSIO_GITHUB_ACCOUNT_ID
)
```

For param details: `composio_get_schema("GITHUB_<ACTION>")`

---

## Issues

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_AN_ISSUE` | Create a new issue |
| `GITHUB_LIST_REPOSITORY_ISSUES` | List issues (filter by state, labels, assignee) |
| `GITHUB_GET_AN_ISSUE` | Get issue details |
| `GITHUB_UPDATE_AN_ISSUE` | Edit issue title, body, state, labels, assignees |
| `GITHUB_CREATE_AN_ISSUE_COMMENT` | Add a comment to an issue |
| `GITHUB_LIST_ISSUE_COMMENTS` | List all comments on an issue |
| `GITHUB_ADD_LABELS_TO_AN_ISSUE` | Add labels |
| `GITHUB_ADD_ASSIGNEES_TO_AN_ISSUE` | Assign people |
| `GITHUB_CREATE_A_LABEL` | Create a label |
| `GITHUB_CREATE_A_MILESTONE` | Create a milestone |
| `GITHUB_ADD_SUB_ISSUE` | Add a sub-issue |
| `GITHUB_CREATE_ISSUE_TYPE` | Create an issue type |
| `GITHUB_CREATE_REACTION_FOR_AN_ISSUE` | React to an issue |
| `GITHUB_CREATE_REACTION_FOR_AN_ISSUE_COMMENT` | React to a comment |

## Pull Requests

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_PULL_REQUEST` | Open a new PR |
| `GITHUB_LIST_PULL_REQUESTS` | List PRs |
| `GITHUB_GET_A_PULL_REQUEST` | Get PR details |
| `GITHUB_MERGE_A_PULL_REQUEST` | Merge a PR |
| `GITHUB_UPDATE_A_PULL_REQUEST` | Edit PR title, body, state |
| `GITHUB_CREATE_A_REVIEW_FOR_A_PULL_REQUEST` | Submit a code review |
| `GITHUB_CREATE_A_REVIEW_COMMENT_FOR_A_PULL_REQUEST` | Inline code comment |
| `GITHUB_CREATE_A_REPLY_FOR_A_REVIEW_COMMENT` | Reply to review comment |
| `GITHUB_CHECK_IF_PULL_REQUEST_HAS_BEEN_MERGED` | Check merge status |
| `GITHUB_CREATE_A_REACTION_FOR_A_PULL_REQUEST_REVIEW_COMMENT` | React to review |

## Repositories

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER` | Create personal repo |
| `GITHUB_CREATE_AN_ORGANIZATION_REPOSITORY` | Create org repo |
| `GITHUB_CREATE_A_REPOSITORY_USING_A_TEMPLATE` | Create from template |
| `GITHUB_CREATE_A_FORK` | Fork a repo |
| `GITHUB_DELETE_A_REPOSITORY` | Delete a repo |
| `GITHUB_GET_A_REPOSITORY` | Get repo details |
| `GITHUB_LIST_ORGANIZATION_REPOSITORIES` | List org repos |
| `GITHUB_LIST_REPOSITORIES_FOR_THE_AUTHENTICATED_USER` | List your repos |
| `GITHUB_ADD_A_REPOSITORY_COLLABORATOR` | Add collaborator |
| `GITHUB_CREATE_A_DEPLOY_KEY` | Add deploy key |
| `GITHUB_CREATE_A_REPOSITORY_DISPATCH_EVENT` | Trigger custom webhook event |
| `GITHUB_CREATE_A_REPOSITORY_WEBHOOK` | Create webhook |
| `GITHUB_CREATE_A_REPOSITORY_RULESET` | Create branch protection rules |
| `GITHUB_CREATE_AN_AUTOLINK_REFERENCE_FOR_A_REPOSITORY` | Autolink external IDs |

## Commits & Files

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` | Create or update a file in a repo |
| `GITHUB_GET_REPOSITORY_CONTENT` | Read file contents from a repo |
| `GITHUB_DELETE_A_FILE` | Delete a file |
| `GITHUB_COMMIT_MULTIPLE_FILES` | Commit multiple files at once |
| `GITHUB_CREATE_A_COMMIT` | Create a commit |
| `GITHUB_CREATE_A_COMMIT_COMMENT` | Comment on a commit |
| `GITHUB_COMPARE_TWO_COMMITS` | Diff two commits |
| `GITHUB_LIST_COMMITS` | List commits on a branch |
| `GITHUB_CREATE_A_BLOB` | Create a blob |
| `GITHUB_CREATE_A_TREE` | Create a tree |

## Branches & Tags

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_REFERENCE` | Create a branch or tag |
| `GITHUB_DELETE_A_REFERENCE` | Delete a branch |
| `GITHUB_LIST_BRANCHES` | List branches |
| `GITHUB_GET_A_BRANCH` | Get branch details |
| `GITHUB_RENAME_A_BRANCH` | Rename a branch |
| `GITHUB_CREATE_A_TAG_OBJECT` | Create a tag |
| `GITHUB_DELETE_A_BRANCH_PROTECTION_RULE` | Remove protection |
| `GITHUB_CREATE_COMMIT_SIGNATURE_PROTECTION` | Require signed commits |

## Releases

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_RELEASE` | Create a release |
| `GITHUB_LIST_RELEASES` | List releases |
| `GITHUB_GET_A_RELEASE` | Get release details |
| `GITHUB_UPDATE_A_RELEASE` | Edit a release |
| `GITHUB_DELETE_A_RELEASE` | Delete a release |
| `GITHUB_DELETE_A_RELEASE_ASSET` | Remove release asset |
| `GITHUB_CREATE_REACTION_FOR_A_RELEASE` | React to a release |

## GitHub Actions & Workflows

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_WORKFLOW_DISPATCH_EVENT` | Trigger a workflow manually |
| `GITHUB_CANCEL_WORKFLOW_RUN` | Cancel a running workflow |
| `GITHUB_LIST_WORKFLOW_RUNS_FOR_A_REPOSITORY` | List all workflow runs |
| `GITHUB_LIST_JOBS_FOR_A_WORKFLOW_RUN` | List jobs in a run |
| `GITHUB_DOWNLOAD_WORKFLOW_RUN_LOGS` | Download run logs |
| `GITHUB_DELETE_WORKFLOW_RUN_LOGS` | Delete logs |
| `GITHUB_RE_RUN_A_WORKFLOW` | Re-run failed workflow |
| `GITHUB_DELETE_ARTIFACT` | Delete an artifact |
| `GITHUB_APPROVE_WORKFLOW_RUN_FOR_FORK_PULL_REQUEST` | Approve fork PR run |

## Secrets & Variables

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_OR_UPDATE_A_REPOSITORY_SECRET` | Set repo secret |
| `GITHUB_DELETE_A_REPOSITORY_SECRET` | Delete repo secret |
| `GITHUB_CREATE_A_REPOSITORY_VARIABLE` | Set repo variable |
| `GITHUB_DELETE_A_REPOSITORY_VARIABLE` | Delete variable |
| `GITHUB_CREATE_OR_UPDATE_AN_ORGANIZATION_SECRET` | Set org secret |
| `GITHUB_CREATE_OR_UPDATE_AN_ENVIRONMENT_SECRET` | Set env secret |
| `GITHUB_CREATE_AN_ENVIRONMENT_VARIABLE` | Set env variable |

## Deployments

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_DEPLOYMENT` | Create a deployment |
| `GITHUB_CREATE_A_DEPLOYMENT_STATUS` | Update deployment status |
| `GITHUB_DELETE_DEPLOYMENT` | Delete a deployment |
| `GITHUB_CREATE_OR_UPDATE_AN_ENVIRONMENT` | Create/update environment |
| `GITHUB_DELETE_ENVIRONMENT` | Delete environment |
| `GITHUB_CREATE_A_GITHUB_PAGES_SITE` | Enable GitHub Pages |
| `GITHUB_CREATE_A_GITHUB_PAGES_DEPLOYMENT` | Deploy to Pages |
| `GITHUB_DELETE_GITHUB_PAGES_SITE` | Delete Pages site |

## Gists

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_GIST` | Create a gist |
| `GITHUB_LIST_GISTS_FOR_THE_AUTHENTICATED_USER` | List your gists |
| `GITHUB_GET_A_GIST` | Get gist details |
| `GITHUB_UPDATE_A_GIST` | Edit a gist |
| `GITHUB_DELETE_GIST` | Delete a gist |
| `GITHUB_CREATE_A_GIST_COMMENT` | Comment on a gist |

## Projects (v2)

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_USER_PROJECT` | Create a project |
| `GITHUB_ADD_ITEM_TO_USER_PROJECT` | Add issue/PR to project |
| `GITHUB_CREATE_DRAFT_ITEM_FOR_USER_PROJECT` | Add draft card |
| `GITHUB_CREATE_VIEW_FOR_USER_PROJECT` | Create a project view |
| `GITHUB_CLEAR_PROJECT_V2_ITEM_FIELD_VALUE` | Clear a field value |
| `GITHUB_ADD_FIELD_TO_USER_PROJECT` | Add a field |

## Organizations & Teams

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_A_TEAM` | Create a team |
| `GITHUB_DELETE_A_TEAM` | Delete a team |
| `GITHUB_ADD_OR_UPDATE_TEAM_MEMBERSHIP_FOR_USER` | Add user to team |
| `GITHUB_ADD_OR_UPDATE_TEAM_REPOSITORY_PERMISSIONS` | Set team repo access |
| `GITHUB_CREATE_A_DISCUSSION` | Create team discussion |
| `GITHUB_CREATE_A_DISCUSSION_COMMENT` | Comment on discussion |
| `GITHUB_BLOCK_USER_FROM_ORGANIZATION` | Block user from org |
| `GITHUB_CONVERT_ORG_MEMBER_TO_OUTSIDE_COLLABORATOR` | Change member type |

## GitHub AI (Copilot / Models)

| Action | What it does |
|--------|-------------|
| `GITHUB_CREATE_INFERENCE_CHAT_COMPLETIONS` | Use GitHub Models for chat |
| `GITHUB_CREATE_INFERENCE_EMBEDDINGS` | Generate embeddings via GitHub Models |

## Common Workflows

**Create an issue:** `GITHUB_CREATE_AN_ISSUE` with `owner`, `repo`, `title`, `body`

**Create a file in a repo:** `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS` with `owner`, `repo`, `path`, `message` (commit msg), `content` (base64-encoded)

**Open a PR:** `GITHUB_CREATE_A_PULL_REQUEST` with `owner`, `repo`, `title`, `head` (branch), `base` (target branch)

**Read a file:** `GITHUB_GET_REPOSITORY_CONTENT` with `owner`, `repo`, `path`

**Trigger a workflow:** `GITHUB_CREATE_A_WORKFLOW_DISPATCH_EVENT` with `owner`, `repo`, `workflow_id`, `ref`

## Rules

- Use `COMPOSIO_GITHUB_ACCOUNT_ID` for `connected_account_id`
- File content must be base64-encoded for `CREATE_OR_UPDATE_FILE_CONTENTS`
- Use `composio_get_schema("GITHUB_<ACTION>")` for unknown params
