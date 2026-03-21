# Changelog

All notable changes to this project will be documented in this file.

## [3.0.0] - 2026-03-21

### Added
- ✨ Backend v3.0 consolidation with multi-platform support
- ✨ Rate limiting integration (slowapi)
- ✨ Batch processing endpoints (create, schedule, publish up to 100 posts)
- ✨ Post publisher service with retry logic (exponential backoff)
- ✨ Alembic database migrations setup
- ✨ GitHub Actions CI/CD pipelines (tests + lint)
- ✨ Pre-commit hooks configuration
- ✨ Pytest configuration and test fixtures
- ✨ Comprehensive README and documentation

### Changed
- 🔄 Updated entry points to use `backend/main.py` as primary
- 🔄 Consolidated `app/` features into `backend/`
- 🔄 Updated requirements.txt with all dependencies
- 🔄 Version bumped from 2.0.0 to 3.0.0

### Fixed
- 🐛 Database configuration in alembic.ini
- 🐛 Route registration in backend/main.py
- 🐛 .gitignore entries for migrations and IDE files

### Deprecated
- 📦 `app/` folder (use `backend/` instead)

## [2.0.0] - 2026-03-18

### Added
- ✨ Multi-platform services (Instagram, TikTok, Facebook, Twitter, LinkedIn, YouTube)
- ✨ JWT authentication
- ✨ Channel management
- ✨ Media upload (Vercel Blob)
- ✨ Cron jobs for scheduled posting
- ✨ Token refresh logic

### Features
- Post CRUD operations
- OAuth flows
- Analytics endpoints
- Batch operations support

## [1.0.0] - 2026-03-15

### Initial Release
- Basic Instagram multipost backend
- CRUD endpoints for posts
- Instagram OAuth integration
- Basic scheduling support
- SQLAlchemy database models

---

## Unreleased

### In Progress
- 🚀 Real platform credential testing
- 📊 Sentry error tracking integration
- 🚀 Vercel auto-deployment
- 🧪 Expanded test suite
- 📈 Performance optimization
- 🎨 Frontend dashboard

### Planned
- TikTok webhook support
- Advanced scheduling (timezone-aware)
- AI caption generation
- Collaboration features
- Team management

---

## How to Use This File

- **Added**: For new features
- **Changed**: For changes in existing functionality
- **Fixed**: For any bug fixes
- **Deprecated**: For soon-to-be removed features
- **Removed**: For removed features
- **Security**: For security improvements

## Versioning

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

---

Last updated: 2026-03-21
