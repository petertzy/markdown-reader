# Project Roles and Responsibilities

This document describes the management and governance roles used by Markdown
Reader. It is intended to make decision-making and points of responsibility
clear to contributors.

These roles describe project responsibilities; they are not a promise that
GitHub can grant each role a separate permission set. This project currently
uses a GitHub personal account, so GitHub's available repository permissions
may not support fine-grained separation between all of these roles. Actual
access is limited to the permissions GitHub provides and the access that the
project owner has granted.

## Current role assignments

| Role | Current members |
| --- | --- |
| Admin | [@petertzy](https://github.com/petertzy), [@lwu1822](https://github.com/lwu1822) |
| Maintainer | [@Eswar0108](https://github.com/Eswar0108), [@karaaslanz](https://github.com/karaaslanz) |
| Reviewer | TBD; currently review is performed by all Admins and Maintainers |
| Contributor | See [`CONTRIBUTORS.md`](../CONTRIBUTORS.md) |

The assignment list is current as of the latest update to this document. A
person may hold more than one role when the project explicitly assigns those
responsibilities.

## Roles and scope of authority

### Admins

Admins are responsible for the project's overall governance. They:

- set or approve project-wide policies and governance changes;
- appoint or remove maintainers and reviewers;
- resolve escalated disputes about project direction, access, or conduct; and
- ensure that governance documentation remains accurate.

Admins may make decisions that affect the project as a whole. Where GitHub
does not offer a separate permission for an Admin responsibility, the project
owner retains the corresponding platform access and the Admin role represents
decision-making authority rather than an independently configurable GitHub
permission. Admins are also responsible for ensuring that pull requests are
reviewed and merged in a timely and appropriate manner, and they participate
directly in that work. Significant decisions should be documented in an issue,
pull request, or other durable project record whenever practical.

### Maintainers

Maintainers are trusted technical stewards of the codebase. They:

- triage issues and help contributors identify appropriate next steps;
- review and merge pull requests within the project's contribution standards;
- maintain the health of the codebase, documentation, tests, and release
  process;
- coordinate technical decisions and communicate changes to contributors; and
- escalate matters that require administrative authority.

Maintainers may recommend, approve, or merge changes when the available GitHub
access and repository workflow allow it. Maintainer status alone does not
guarantee a separate GitHub permission level. Maintainers do not appoint
project roles unless an Admin has delegated that authority. Reviewing and
merging pull requests is a core Maintainer responsibility, and all Maintainers
currently participate directly in this work.

### Reviewers

The project does not currently have a separate Reviewer group. Until there is
enough review capacity to establish one, Admins and Maintainers collectively
handle all project review and merge work.

In the future, dedicated Reviewers may provide focused review of pull requests
and proposed changes while continuing to share responsibility for moving
approved pull requests through the merge process. They would:

- assess correctness, maintainability, security, documentation, and test
  coverage as relevant to a change;
- provide actionable feedback and identify risks or unresolved questions; and
- confirm when a change is ready for maintainer consideration.

Reviewers may request changes, approve work, and merge pull requests when the
repository workflow and available GitHub access allow it. Reviewer approval is
advisory unless the applicable branch protection or project decision makes it
a required approval. All management roles and Reviewers are expected to help
ensure that pull requests are reviewed and merged; establishing a dedicated
Reviewer group is a long-term goal and is expected to require sustained growth
in the project's review capacity, not an immediate organizational change.

### Contributors

For the project's contributor list, see
[`CONTRIBUTORS.md`](../CONTRIBUTORS.md). Contribution guidelines and the
process for proposing changes are documented in
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Adding or removing members

1. A role change should be proposed in a public issue or pull request, with a
   short explanation of the person's contributions and the scope of the
   requested authority.
2. An Admin must approve appointments to Admin or Maintainer. Once a dedicated
   Reviewer group is established, an Admin or Maintainer may nominate a
   Reviewer, subject to Admin confirmation.
3. The affected member should be informed of the responsibilities and access
   associated with the role before the change is applied.
4. An Admin updates this document and, where applicable, the available GitHub
   access settings after approval. The change record should link to the issue
   or pull request when possible.
5. Members may be removed when they request it, become inactive, no longer
   need the associated access, or fail to meet the project's contribution and
   conduct expectations. Admins should remove access promptly when a role ends.

Role assignments should be reviewed periodically and whenever the project's
ownership or repository permissions change. Temporary delegation should be
clearly labelled with its scope and end date.

## Decision-making principles

- Use the least authority necessary for a decision or repository action.
- Prefer open discussion and documented rationale for decisions that affect
  contributors or project direction.
- Coordinate technical review and repository administration openly where
  practical.
- Escalate conflicts of interest or unresolved disputes to an Admin.
- Keep this document aligned with the actual access available through GitHub.
