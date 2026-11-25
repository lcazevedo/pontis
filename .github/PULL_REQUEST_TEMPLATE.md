## Summary
<!-- Briefly describe what this pull request changes and why. -->

## Related Issue
<!-- e.g. Closes #12 -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation / translation
- [ ] Packaging / CI / maintenance

## How Was This Tested?
<!-- Mention local tests, temporary folders, or AppImage verification performed. -->

## Checklist
- [ ] Every new Python file includes `# SPDX-License-Identifier: GPL-3.0-or-later`
- [ ] `pytest` (`QT_QPA_PLATFORM=offscreen pytest`) passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy` passes in strict mode
- [ ] Any new UI strings were added to both `en` and `pt_BR` in `src/pontis/i18n/__init__.py`
- [ ] No credentials, tokens, or real user data are included
