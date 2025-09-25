````markdown
# Contributing to OpenCRAVAT

Thank you for considering contributing to OpenCRAVAT!

OpenCRAVAT is an open-source platform for genomic variant annotation and prioritization.  
We welcome contributions from the community — whether you're fixing a typo, developing a new annotator, reporting bugs, or proposing new features.  

This document provides guidelines and expectations to make contributing clear and transparent for everyone.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)  
- [Ways to Contribute](#ways-to-contribute)  
- [Getting Started](#getting-started)  
- [Development Workflow](#development-workflow)  
- [Coding Guidelines](#coding-guidelines)  
- [Module Development](#module-development)  
- [Reporting Issues](#reporting-issues)  
- [Pull Requests](#pull-requests)  
- [Community and Support](#community-and-support)

---

## Code of Conduct

By participating in this project, you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).  
Please help us foster a positive and respectful environment for everyone.

---

## Ways to Contribute

There are many ways to help:

- **Reporting bugs**: Let us know if you encounter unexpected behavior.  
- **Suggesting features**: Share ideas to improve usability or functionality.  
- **Documentation**: Improve tutorials, READMEs, or add new examples.  
- **Code contributions**: Fix bugs, add features, or improve efficiency.  
- **Modules**: Build and share annotators, converters, and reporters.  
- **Community support**: Answer questions on GitHub Discussions, BioStars, or other forums.

No contribution is too small — all efforts help the community.

---

## Getting Started

1. **Fork the repository**: Start by making your own copy.  
2. **Clone your fork**:  
   ```bash
   git clone https://github.com/<your-username>/open-cravat.git
   cd open-cravat
````

3. **Set up your environment**:

   ```bash
   pip install -r requirements.txt
   ```
4. **Run the test suite**:

   ```bash
   pytest
   ```

Check the [documentation](https://open-cravat.readthedocs.io/) for installation and usage details.

---

## Development Workflow

We follow a simple GitHub flow:

1. **Create a branch**:

   ```bash
   git checkout -b my-feature
   ```
2. **Make changes**: Commit clearly and often.
3. **Write tests**: Add or update unit tests when appropriate.
4. **Run tests**: Ensure everything passes locally.
5. **Open a Pull Request (PR)**: Submit your branch to `main` with a clear description.

---

## Coding Guidelines

* Follow **PEP8** style for Python.
* Keep functions modular and documented.
* Write clear commit messages (e.g., `fix: correct variant position parsing`).
* Add docstrings for public functions and classes.
* Update relevant documentation when introducing changes.

---

## Module Development

OpenCRAVAT supports community-built modules (annotators, converters, reporters).
To contribute a module:

1. Use `oc new annotator my_annotator` (or reporter/converter) to generate a template.
2. Fill in the `yml` metadata and implement logic in `__init__.py`.
3. Test the module locally with sample inputs.
4. Submit your module to the [OpenCRAVAT Module Store](https://open-cravat.readthedocs.io/en/latest/Module-Store.html).

See the [developer guide](https://open-cravat.readthedocs.io/) for detailed instructions.

---

## Reporting Issues

We use GitHub Issues to track bugs, feature requests, and tasks.
When filing an issue, please include:

* A **descriptive title**.
* Steps to reproduce the problem.
* Expected vs. actual behavior.
* Environment details (OS, Python version, OpenCRAVAT version).

Search existing issues before creating a new one.

---

## Pull Requests

* Keep PRs small and focused when possible.
* Describe the problem and solution in the PR body.
* Reference related issues (e.g., `Fixes #123`).
* Ensure all tests pass before submission.
* Be responsive to feedback from maintainers and contributors.

---

## Community and Support

OpenCRAVAT thrives on community involvement.
You can connect with us through:

* [GitHub Discussions](https://github.com/KarchinLab/open-cravat/discussions)
* [BioStars](https://www.biostars.org/) (tag: `opencravat`)
* [Documentation](https://open-cravat.readthedocs.io/)

---

## Acknowledgements

This guide was adapted from:

* [Mozilla Science Lab: Contributing Guidelines](https://mozillascience.github.io/working-open-workshop/contributing/)
* [Atom’s Contributing Guide](https://github.com/atom/atom/blob/master/CONTRIBUTING.md)

---

Thank you for contributing to OpenCRAVAT!

```
