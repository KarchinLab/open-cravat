---
name: Good First Issue
about: 'Good first issues for new contributors. '
title: ''
labels: ''
assignees: ''

---

name: "Good First Issue"
description: "A small, well-defined issue ideal for first-time contributors"
title: "[Good First Issue]: "
labels:
  - good first issue
  - help wanted
body:
  - type: markdown
    attributes:
      value: |
        👋 **Welcome to OpenCRAVAT!**  
        Thank you for your interest in contributing.  
        Please use this template to describe a beginner-friendly issue clearly and completely.

  - type: input
    id: summary
    attributes:
      label: Short Summary
      description: Provide a short, descriptive title for the issue.
      placeholder: e.g., "Add screenshots to the Single Variant Reporter tutorial"
    validations:
      required: true

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Explain what this issue is about and why it’s useful. Include links to relevant files, docs, or examples.
      placeholder: |
        Example:
        The Single Variant Reporter tutorial currently lacks screenshots. 
        Adding them will make the documentation more user-friendly and help new users understand the interface.
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to Complete
      description: Provide a simple step-by-step guide to complete the task.
      placeholder: |
        1. Fork and clone the repo
        2. Edit `docs/tutorials/single_variant_reporter.md`
        3. Add screenshots and descriptions
        4. Preview changes locally
        5. Submit a pull request
    validations:
      required: false

  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance Criteria
      description: Define the success criteria for completing this issue.
      placeholder: |
        - [ ] Screenshots are clear and properly formatted
        - [ ] Images are added to the correct folder
        - [ ] Documentation builds successfully
    validations:
      required: true

  - type: dropdown
    id: difficulty
    attributes:
      label: Difficulty Level
      description: Choose the expected difficulty for this issue.
      options:
        - 🟢 Easy (Documentation or small code fix)
        - 🟡 Intermediate (Feature addition or testing)
        - 🔴 Advanced (New module, significant refactor)
    validations:
      required: true

  - type: textarea
    id: resources
    attributes:
      label: Helpful Resources
      description: Add links to related docs, files, or guides that will help the contributor.
      placeholder: |
        - [Contributing Guide](../CONTRIBUTING.md)
        - [Code of Conduct](../CODE_OF_CONDUCT.md)
        - [Documentation](https://open-cravat.readthedocs.io/)
        - [Example Modules](https://github.com/KarchinLab/open-cravat-modules)
    validations:
      required: false

  - type: markdown
    attributes:
      value: |
        ---
        **Before submitting this issue:**
        - Confirm that this issue is beginner-friendly.
        - Include clear instructions and acceptance criteria.
        - Tag with `good first issue` and `help wanted`.

         *Thank you for helping new contributors get started with OpenCRAVAT!*
