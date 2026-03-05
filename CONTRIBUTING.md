# Contributing to Universal Memory Engine (UME)

Thank you for considering contributing to the Universal Memory Engine project! We welcome contributions from the community.

Before participating, please take a moment to read our [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Architecture Decision Records can be found in the [adr/](adr) directory for additional project context.

## How to Contribute

We encourage contributions of all kinds, including bug reports, feature requests, documentation improvements, and code contributions.

### Reporting Bugs or Requesting Features

If you find a bug or have an idea for a new feature, please check our issue tracker on GitHub to see if it has already been reported. If not, please open a new issue, providing as much detail as possible.

*   **For Bug Reports:** Include steps to reproduce the bug, expected behavior, and actual behavior.
*   **For Feature Requests:** Clearly describe the proposed feature and its potential benefits.

### Code Contributions

1.  **Fork the Repository:** Start by forking the main UME repository to your GitHub account.
2.  **Create a Branch:** For any new feature or bug fix, create a new branch in your fork. Choose a descriptive branch name (e.g., `fix/some-bug` or `feat/new-feature`).
    ```bash
    git checkout -b your-branch-name
    ```
3.  **Make Changes:** Implement your changes, ensuring your code follows any existing style guidelines (e.g., run linters if configured). Add or update tests as appropriate.
4.  **Commit Your Changes:** Write clear and concise commit messages.
    ```bash
    git commit -m "feat: Add new feature X" -m "Detailed description of changes."
    ```
5.  **Push to Your Fork:**
    ```bash
    git push origin your-branch-name
    ```
6.  **Submit a Pull Request (PR):** Open a pull request from your branch to the main UME repository. Provide a clear description of your changes in the PR.

### Runtime bootstrap expectations

- Keep `import ume` side-effect minimal (core API/types only).
- Entry points (CLI, API servers, workers) must call
  `ume.bootstrap.runtime.bootstrap_runtime("ume")` before using optional
  integrations such as vector backends, embedding listeners, plugin loaders, or
  optional graph adapters.
- Compatibility re-exports in `ume.__init__` are temporary deprecation shims;
  prefer direct module imports in new contributions.

### Coding Style

- **Black** is used for code formatting. Run `black` on your changes before committing.
- **Ruff** enforces linting rules and also checks formatting. The CI will fail if Ruff reports issues.
- **Mypy** performs static type checking. The CI runs `poetry run mypy` and will fail on type errors.

### Branch Naming & Pre-commit Hooks

- Create branches using the pattern `feat/`, `fix/`, `docs/`, or `chore/` followed by a short description, e.g. `feat/add-api-endpoint`.
- Install the Git hooks once per clone:
  ```bash
  pre-commit install
  ```
  Afterwards `pre-commit` will run automatically on each commit. You can manually run all hooks with:
  ```bash
  pre-commit run --all-files
  ```

The pre-commit configuration includes a `detect-secrets` hook to prevent
accidentally committing credentials. Generate or update the baseline with:
```bash
detect-secrets scan > .secrets.baseline
```
To scan specific files manually you can run:
```bash
pre-commit run detect-secrets --files path/to/file
```

### Pull Requests

 - Ensure `pre-commit` hooks pass and that `pytest` succeeds before opening a PR. Unit tests must run with coverage reporting, verified with:
   ```bash
   pytest --cov=ume --cov-fail-under=30
   ```
- All PRs are reviewed by a maintainer and must pass CI (tests, Ruff lint, formatting checks, and mypy) before merging.
- The CI workflow automatically skips these checks when a pull request only modifies documentation or code comments.

### Security checklist for new routes/events/adapters

For any contribution that introduces a new API route, event type, or transport adapter,
complete this checklist before opening a PR:

- [ ] AuthN is implemented and fails closed (`401`) for missing/invalid credentials.
- [ ] AuthZ is implemented and denies unauthorized actor/role/group access (`403`).
- [ ] Mutations flow through the canonical event processor/policy pipeline (no direct bypass ingress).
- [ ] Deny outcomes are consistent with CLI/API/Kafka/gRPC decision semantics.
- [ ] Privileged operations emit signed audit records containing actor identity and correlation IDs.
- [ ] Tests include threat-model bypass cases (for example, direct mutation path skipping policy).

### Graph Backend Extensibility

Graph store backends are selected through `create_graph_adapter()` in
`src/ume/factories.py`, not through an adapter map such as
`ume.adapters._ADAPTERS`.

- `UME_GRAPH_BACKEND` is the switch that selects the graph implementation.
- New graph backends must be wired directly into `create_graph_adapter()`.
- `src/ume/integrations/registry.py` is for integration adapters (e.g.,
  third-party client integrations), and is not used for graph storage
  backend selection.

#### How to add a graph backend

When contributing a new graph backend, include all of these touch points:

1. Add a new adapter class implementing `IGraphAdapter` in `src/ume/`.
2. Add a factory branch in `src/ume/factories.py::create_graph_adapter` keyed
   by a new `UME_GRAPH_BACKEND` value.
3. Add/extend tests:
   - `tests/test_factories.py` for backend dispatch from `UME_GRAPH_BACKEND`.
   - backend-specific adapter tests (following existing graph adapter test
     patterns) for CRUD/query behavior.

### Merge Queue

Merging is handled automatically using GitHub's merge queue. After your pull request is approved and the required checks pass, it will enter the queue and merge once it reaches the front. This ensures every PR is tested with the latest `main` branch before being merged.

## Development Setup

Please refer to the `README.md` for instructions on setting up your development environment.

## Development Workflow

1. Install dependencies, including dev tools, using Poetry:
   ```bash
   poetry install --with dev
   ```
2. Install pre-commit hooks:
   ```bash
 pre-commit install
  ```
   This installs the `detect-secrets` hook along with other checks.
   If you update `.secrets.baseline`, commit the refreshed file so CI uses the latest baseline.
3. Create a feature branch and implement your changes.
4. Before committing, run the checks locally:
   ```bash
  pre-commit run --all-files
  poetry run pytest
   ```
5. Push your branch and open a pull request.

### Full Test Suite

Some tests rely on optional dependencies provided by extras.
Install them all and run the suite with:
```bash
poetry install --with dev --all-extras
poetry run pytest
```
This exercises vector search, embedding, and gRPC server functionality.

## Questions?

If you have any questions, feel free to ask by opening an issue.

We appreciate your contributions to making UME better!
