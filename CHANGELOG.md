# CHANGELOG

<!-- version list -->

## v0.9.4 (2026-02-25)

### Bug Fixes

- Whitelist MCP server URL as allowed audience for dynamic client registration
  ([`c97501b`](https://github.com/SelfMemory/SelfMemory/commit/c97501b24272ac50272eeb1a8539b7fef1c900d8))


## v0.9.3 (2026-02-25)

### Bug Fixes

- Include decryption of API keys in the project API keys listing
  ([`3405cd5`](https://github.com/SelfMemory/SelfMemory/commit/3405cd5e7e46c5e40d8f54eb520568745c50e318))

- Update selfmemory version to 0.9.2 in uv.lock
  ([`311e8bb`](https://github.com/SelfMemory/SelfMemory/commit/311e8bb230ee02bcc6c5177c088982d90492a9b1))

### Build System

- **deps**: Bump the npm_and_yarn group across 1 directory with 3 updates (#128)
  ([#128](https://github.com/SelfMemory/SelfMemory/pull/128),
  [`256148b`](https://github.com/SelfMemory/SelfMemory/commit/256148bc14ae41c5ea26c3e457b5aac2e37be9b8))

### Chores

- **deps**: Bump the npm_and_yarn group across 1 directory with 2 updates
  ([`8063021`](https://github.com/SelfMemory/SelfMemory/commit/806302156c4f3999a45613062b9313183d8a1bfa))


## v0.9.2 (2026-02-25)

### Bug Fixes

- Add coverage and test analytics reporting to CI workflow
  ([`367b7ad`](https://github.com/SelfMemory/SelfMemory/commit/367b7ad59ee20bf32bdbeaf56913585415e17428))


## v0.9.1 (2026-02-24)

### Bug Fixes

- Remove unused import from api_keys.py and update selfmemory version to 0.9.0 in uv.lock
  ([`d670e45`](https://github.com/SelfMemory/SelfMemory/commit/d670e4561e8961bab9f66d59a3d122a2f8857ab7))

### Refactoring

- Remove unused get_user_project_permissions function and simplify API key retrieval
  ([`f2da47d`](https://github.com/SelfMemory/SelfMemory/commit/f2da47da01d909338677d040d6b1eb0678147e0a))


## v0.9.0 (2026-02-24)

### Bug Fixes

- Suppress E402 lint errors for intentional late imports in MCP server
  ([`1d56eeb`](https://github.com/SelfMemory/SelfMemory/commit/1d56eeb4fb39cb1dddc2a15e24e7dc9829a057cd))

- Update environment variable loading paths and remove deprecated .env.example file
  ([`ece5edb`](https://github.com/SelfMemory/SelfMemory/commit/ece5edb6e73882b19ed4ab3ca50664a0a0f227a5))

- Update OpenTelemetry initialization print statement for better readability
  ([`94242b0`](https://github.com/SelfMemory/SelfMemory/commit/94242b095fdbf35989be87f0fafa58604167caeb))

### Features

- Add @selfmemory/sdk TypeScript SDK with tests
  ([`a8be806`](https://github.com/SelfMemory/SelfMemory/commit/a8be8065da6ef822645020200ce2e0a251ae3956))


## v0.8.5 (2026-02-24)

### Bug Fixes

- Resolve 421 Misdirected Request by configuring MCP transport security allowed hosts
  ([`1613056`](https://github.com/SelfMemory/SelfMemory/commit/161305654af81f3f24fbfd79737f72b55421e020))

### Continuous Integration

- **deps**: Bump actions/upload-artifact from 4 to 6
  ([`d35df5d`](https://github.com/SelfMemory/SelfMemory/commit/d35df5df9212834f74d04ea74a0e1c9bee6a70d8))


## v0.8.4 (2026-02-24)

### Bug Fixes

- Replace setuptools-scm with static versioning to prevent post-release suffixes
  ([`16f7ffa`](https://github.com/SelfMemory/SelfMemory/commit/16f7ffa3c5e235d40e8810cf1bb2446a79e5fe5a))


## v0.8.3 (2026-02-24)

### Bug Fixes

- **ci**: Add issue templates for bug reports and feature requests, configure CI workflows, and
  enhance README with badges
  ([`8ae2de3`](https://github.com/SelfMemory/SelfMemory/commit/8ae2de3a7797ee74ea2612415c1e7d38ac4583c1))

### Chores

- Remove CodeQL workflow configuration
  ([`7a250a4`](https://github.com/SelfMemory/SelfMemory/commit/7a250a473548c6b70a3cfc6f104d1a1c2514f398))


## v0.8.2 (2026-02-24)

### Bug Fixes

- Sanitize registration response and prevent redirect consumption in Hydra client
  ([`23099e0`](https://github.com/SelfMemory/SelfMemory/commit/23099e0a4af87cb1ca81a9c9ece88fc15802a94b))

- Update build command to use pip for installation and building
  ([`5a1af82`](https://github.com/SelfMemory/SelfMemory/commit/5a1af82768401f2b12e6b9c535ac02bc45c046e2))

- Update MCP server commands for clarity and add development mode support
  ([`4454c83`](https://github.com/SelfMemory/SelfMemory/commit/4454c831df60021d4f15e29fc8173138ad5fa2ba))

### Refactoring

- Code structure for improved readability and maintainability
  ([`7050513`](https://github.com/SelfMemory/SelfMemory/commit/705051313e3f7601f20a69a6f31096479520b44e))


## v0.8.1 (2026-02-23)

### Bug Fixes

- Enhance OpenTelemetry setup with logging support and configuration improvements
  ([`657fe3a`](https://github.com/SelfMemory/SelfMemory/commit/657fe3a00d045b55651397ce3ed2a664d0c48c69))

### Refactoring

- Improve logging initialization format in OpenTelemetry setup
  ([`15bb96b`](https://github.com/SelfMemory/SelfMemory/commit/15bb96b52fd585e38b7b0b542e3f3dcd2e317551))


## v0.8.0 (2026-02-23)

### Features

- Add new API endpoints for memory statistics and enhance client functionality
  ([`d56bc20`](https://github.com/SelfMemory/SelfMemory/commit/d56bc20eccfc8645364a8c7409a24953225af480))

### Refactoring

- Improve code formatting for better readability in main and test files
  ([`2656975`](https://github.com/SelfMemory/SelfMemory/commit/2656975a814cc9636efbcbcb95f40ba4898ddc36))


## v0.7.1 (2026-02-22)

### Bug Fixes

- Enhance invitation email button styling for better visibility
  ([`bdda06e`](https://github.com/SelfMemory/SelfMemory/commit/bdda06ef7a88e6dd95b871a5d6b2fec565a462e0))

- Implement memory encryption and decryption for sensitive data
  ([`5d02055`](https://github.com/SelfMemory/SelfMemory/commit/5d020554da805055fb89c961227a88f4346eaa00))

### Refactoring

- Streamline encryption payload calls in memory management
  ([`846734c`](https://github.com/SelfMemory/SelfMemory/commit/846734cdad5908d4c2bc3acf6f302fc6066c0b40))


## v0.7.0 (2026-02-22)

### Bug Fixes

- Simplify readiness check logic for Qdrant health status
  ([`7f7ca1a`](https://github.com/SelfMemory/SelfMemory/commit/7f7ca1a04fc0d4b62a932cfb23b0d03a767b1470))

- Update CI workflow to install dependencies with dev extras instead of test extras
  ([`d49dfe3`](https://github.com/SelfMemory/SelfMemory/commit/d49dfe3976f88caa2b3863c62560e3dfc4c7e395))

- Update CI workflow to install dependencies with test extras instead of dev extras
  ([`8a217f6`](https://github.com/SelfMemory/SelfMemory/commit/8a217f6e9285abd326cb62f4a86236b80a919af8))

### Chores

- Update Docusaurus dependencies to version 3.9.2 and TypeScript to 5.9.3; add new plugins and
  update sidebars
  ([`695d168`](https://github.com/SelfMemory/SelfMemory/commit/695d168e140469f710d7f482a0e9e84b9beec22d))

### Features

- Implement health check for Ollama service and validate connectivity on startup
  ([`ac0582f`](https://github.com/SelfMemory/SelfMemory/commit/ac0582f85d3ea9dc37a11d8d77ad438af7879b90))

### Refactoring

- Remove outdated tests for API documentation security features
  ([`43e7806`](https://github.com/SelfMemory/SelfMemory/commit/43e78061483fdee413dcd74f86a76d9483a2d69f))


## v0.6.0 (2026-02-22)

### Bug Fixes

- Update API key validation endpoint and improve model availability checks
  ([`fad9602`](https://github.com/SelfMemory/SelfMemory/commit/fad96021ed135ea7ff789b28a92fdec607ce412b))

### Continuous Integration

- **deps**: Bump actions/checkout from 5 to 6
  ([`9a12d60`](https://github.com/SelfMemory/SelfMemory/commit/9a12d60b1e555567498c6088d1d6a879d0249781))

- **deps**: Bump actions/upload-artifact from 4 to 6
  ([`3a837fc`](https://github.com/SelfMemory/SelfMemory/commit/3a837fcfbda5f47c36de635c17bf196f7458bdbe))

### Features

- Add CHANGELOG and update README with banner and links
  ([`54dddef`](https://github.com/SelfMemory/SelfMemory/commit/54dddef5d5fb4c41a8d039ee2b2fd87c3c4cb95c))


## v0.5.2 (2025-12-22)

### Bug Fixes

- Add testing dependencies for improved test coverage
  ([`2561ff4`](https://github.com/SelfMemory/SelfMemory/commit/2561ff4df48ec64510d6c1397911ec1d41f99293))

- Disable API documentation in production for security reasons
  ([`5b5f742`](https://github.com/SelfMemory/SelfMemory/commit/5b5f74271deaa2120a04539869fa10cafa575f12))

- Format logging messages for API documentation status in production and development modes
  ([`1aff302`](https://github.com/SelfMemory/SelfMemory/commit/1aff302f87fd3867f331a24f504e93de02f01a21))

- Streamline environment configuration and enhance security for API documentation
  ([`97ea8a5`](https://github.com/SelfMemory/SelfMemory/commit/97ea8a5459f66b7d808f1c64f9a88f0d1136cb48))

- Update release workflow and documentation for UV integration
  ([`ea85959`](https://github.com/SelfMemory/SelfMemory/commit/ea85959741c09fd83ec427b5a1420f7d97dde1c3))

### Build System

- **deps**: Bump js-yaml
  ([`1567475`](https://github.com/SelfMemory/SelfMemory/commit/15674757be64cd27404e6aeee735d79205b42bd8))

### Continuous Integration

- **deps**: Bump actions/setup-node from 5 to 6
  ([`8030767`](https://github.com/SelfMemory/SelfMemory/commit/80307675d7c7e5e7e2018ad309c9f8bdb8bbb7c0))

- **deps**: Bump actions/setup-python from 5 to 6
  ([`aa4b5f6`](https://github.com/SelfMemory/SelfMemory/commit/aa4b5f61bc4065dd18504f23d5a92b2c5713ad3b))


## v0.5.1 (2025-12-21)

### Bug Fixes

- Enhance streaming response handling in chat API
  ([`0408b3e`](https://github.com/SelfMemory/SelfMemory/commit/0408b3eccc9768ec57e8f17c8a8334f746f971a7))

- Yield content immediately for streaming in chat response
  ([`cdefd09`](https://github.com/SelfMemory/SelfMemory/commit/cdefd0929b88034c33d497dad78a2209133290da))


## v0.5.0 (2025-12-21)

### Bug Fixes

- Add cursor support for MCP integration
  ([`e0038f3`](https://github.com/SelfMemory/SelfMemory/commit/e0038f30fd5eb9fd961d56e0a3d1cad47cdcc0ff))

- Add wait for required status checks before release
  ([`4b4698a`](https://github.com/SelfMemory/SelfMemory/commit/4b4698a2411fe56a9a7bf593f5c62fb954463366))

- Ensure proper handling of release conditions in workflow
  ([`a2466ee`](https://github.com/SelfMemory/SelfMemory/commit/a2466eed18699b1c12cbb7f046fda334348d83b9))

### Chores

- Update code structure for better readability and maintainability
  ([`07890cb`](https://github.com/SelfMemory/SelfMemory/commit/07890cbebffdd0dddbd0e783309bebc7015b11c0))

### Features

- Implement Google Matching Engine and Weaviate vector stores
  ([`6249a7c`](https://github.com/SelfMemory/SelfMemory/commit/6249a7c4210a1b996855188c0ed15a4434247f58))

### Refactoring

- Clean up whitespace and streamline code formatting in Qdrant class
  ([`a5c42c0`](https://github.com/SelfMemory/SelfMemory/commit/a5c42c0720a969ffc3ca5de5f06d982502d65a83))

- Improve code formatting and readability in test_qdrant.py
  ([`c4586f5`](https://github.com/SelfMemory/SelfMemory/commit/c4586f5b9083d7d913597eae40756fd7a345eff8))

- Streamline debug print statements in memory search tool call
  ([`a0bafcc`](https://github.com/SelfMemory/SelfMemory/commit/a0bafcc1ce85b18569753bd6dba7d0a332f09056))


## v0.4.5 (2025-11-29)

### Bug Fixes

- Add initial glama.json configuration file for MCP support | #112
  ([`a316c5a`](https://github.com/SelfMemory/SelfMemory/commit/a316c5a037b2059e86e09ca5036c675a5e18685a))

### Documentation

- Add MCP Setup Guide documentation for authentication implementation | #112
  ([`53c1a86`](https://github.com/SelfMemory/SelfMemory/commit/53c1a86b704f2718f778e36e4bffd16def123e43))


## v0.4.4 (2025-11-29)

### Bug Fixes

- Clean up whitespace and improve readability in multiple files
  ([`8e41fdb`](https://github.com/SelfMemory/SelfMemory/commit/8e41fdb0247217f12191e7270f3832581eb81795))

- Improve readability in looks_like_jwt function by formatting return statement
  ([`fb1d36e`](https://github.com/SelfMemory/SelfMemory/commit/fb1d36e383271b323cb1e5d3aaf25a6fbab16bbd))

- Update project description for clarity and consistency
  ([`f916e1a`](https://github.com/SelfMemory/SelfMemory/commit/f916e1aba15642d298378537c3e7435cc3a4b219))

- **auth**: Enhance unified authentication middleware for OAuth and API key support
  ([`50ef2f0`](https://github.com/SelfMemory/SelfMemory/commit/50ef2f012a83a3eeb2eac7d38aab1e23eb4aa677))

- **auth**: Refactor unified authentication middleware documentation and remove unused code
  ([`c643dc3`](https://github.com/SelfMemory/SelfMemory/commit/c643dc3e7f8dd9eca5de373602ee691879018b4b))

### Documentation

- Add MCP Server Configuration Guide documentation
  ([`7acb609`](https://github.com/SelfMemory/SelfMemory/commit/7acb609154e982c49a816dad4182418deb1cbd82))


## v0.4.3 (2025-11-25)

### Bug Fixes

- Address authentication issue in UnifiedAuthMiddleware
  ([`ae4e2cc`](https://github.com/SelfMemory/SelfMemory/commit/ae4e2cc055e643afa6e8941488b5ae577f6c7b65))

- Remove unnecessary whitespace in _hash_token function docstring
  ([`9bc3f05`](https://github.com/SelfMemory/SelfMemory/commit/9bc3f0583253b5e90e53b55c8c09dfa2606d0e1c))

- Update token hashing method to use SHA256 for cache keys
  ([`b872636`](https://github.com/SelfMemory/SelfMemory/commit/b87263679f3a43524695ed067e53cc34366e5da9))


## v0.4.2 (2025-11-25)

### Bug Fixes

- Add SMTP test email and connectivity scripts with client caching for performance optimization
  ([`42de0d1`](https://github.com/SelfMemory/SelfMemory/commit/42de0d1d98e725fd488fa8169058ce2d37047c1f))

- Centralize client caching logic to eliminate DRY violations
  ([`0eb8fad`](https://github.com/SelfMemory/SelfMemory/commit/0eb8fadb1ed9d0c1a5b7092d9525482afbfa3a4f))

- Optimize client caching and improve performance across multiple modules
  ([`02861dd`](https://github.com/SelfMemory/SelfMemory/commit/02861ddfdae62517c5467ee5ea26430d51122f59))


## v0.4.1 (2025-11-25)

### Bug Fixes

- Add token scope validation and caching utilities for improved security
  ([`d70a296`](https://github.com/SelfMemory/SelfMemory/commit/d70a2967435b7aab2e52de20c3486455f0bf1d6f))

- Implement token caching for OAuth and API key validation
  ([`c4eef68`](https://github.com/SelfMemory/SelfMemory/commit/c4eef683a50cc29ae3861cb989568c9a85bd9956))

- Update documentation for token validation and telemetry utilities
  ([`f68aefc`](https://github.com/SelfMemory/SelfMemory/commit/f68aefcdf6c6369cac4c8d4286545ce48b9f0543))

- **logging**: Configure logging settings for improved error tracking
  ([`6c304f1`](https://github.com/SelfMemory/SelfMemory/commit/6c304f1ad8efb583e68b40f19365f6f1dc9a8f3c))

- **telemetry**: Integrate logging and OpenTelemetry initialization for improved monitoring
  ([`57ca3c7`](https://github.com/SelfMemory/SelfMemory/commit/57ca3c7c8630dc30218c3d29c40137faef4cb957))


## v0.4.0 (2025-11-18)

### Features

- Implement notifications management and user invitation acceptance notifications | #90 |
  [@shrijayan]
  ([`16c7d21`](https://github.com/SelfMemory/SelfMemory/commit/16c7d21e00bf29cc1a0beb5c4bbb020bf7eb07c9))


## v0.3.1 (2025-11-17)

### Bug Fixes

- **docs**: Add changelog reference to README.md
  ([`7cd56f0`](https://github.com/SelfMemory/SelfMemory/commit/7cd56f0879d52c12713f184e7c2e3ddfc82edbd8))


## v0.3.0 (2025-11-17)

### Features

- **ci**: Add automated release workflow | #123 | [@shrijayan]
  ([`140fc49`](https://github.com/SelfMemory/SelfMemory/commit/140fc497ac131a127639c070c1c4bf65d6e794f4))


## v0.2.0 (2025-11-17)

### Bug Fixes

- Add a blank line for improved readability in version handling | #76 | [@shrijayan]
  ([`da8e123`](https://github.com/SelfMemory/SelfMemory/commit/da8e123e1781387c1cefd24d1a51e6f7e75316ed))

- **docs**: Remove changelog configuration from pyproject.toml | #79 | [@shrijayan]
  ([`9b3300b`](https://github.com/SelfMemory/SelfMemory/commit/9b3300bf94a5da832e3917489e7b4d67bd251ce5))

- **docs**: Update changelog entry type from doc to link in sidebars configuration
  ([`16a7a55`](https://github.com/SelfMemory/SelfMemory/commit/16a7a55d10fcdf5980522c5e66273c10fe8baf5c))

- **release**: Add GitHub Actions workflow for automated PyPI release and update contributing
  guidelines | #34 | [@shrijayan]
  ([`f12b22a`](https://github.com/SelfMemory/SelfMemory/commit/f12b22addbeb1b2be4057a3f2bf9bb69cc3c677a))

- **release**: Update GitHub Actions to use PAT for bypassing branch protection | #70 | [@shrijayan]
  ([`2f39124`](https://github.com/SelfMemory/SelfMemory/commit/2f391247c00442527d9109606e709aff3f3aeb45))

- **release**: Update GitHub Actions to use standard token for release creation and bypass branch
  protection | #75 | [@shrijayan]
  ([`7b6adcc`](https://github.com/SelfMemory/SelfMemory/commit/7b6adcc54efeb2e8e576103da1012033dc3eddcf))

### Continuous Integration

- **deps**: Bump actions/checkout from 4 to 5
  ([`c54e3fb`](https://github.com/SelfMemory/SelfMemory/commit/c54e3fb5781b1584f5b594e0c13e8c3c62d2b50a))

- **deps**: Bump actions/checkout from 4 to 5
  ([`ba90c63`](https://github.com/SelfMemory/SelfMemory/commit/ba90c63ad55bcbe123887f08610c416f3a4fbfd7))

- **deps**: Bump actions/setup-node from 4 to 5
  ([`609b4ba`](https://github.com/SelfMemory/SelfMemory/commit/609b4ba82ded10d01b509db718369cc2acdda283))

- **deps**: Bump actions/setup-python from 5 to 6
  ([`643d3ac`](https://github.com/SelfMemory/SelfMemory/commit/643d3ac5e15c8dab79bf21fa32efce532471d0ae))

- **deps**: Bump actions/upload-artifact from 4 to 5
  ([`22e60a1`](https://github.com/SelfMemory/SelfMemory/commit/22e60a12cc85d0c7b433d02d116977d38bf3a862))

- **deps**: Bump actions/upload-pages-artifact from 3 to 4
  ([`cae6257`](https://github.com/SelfMemory/SelfMemory/commit/cae6257a6acde233c9aad79534104a4e0dfc5515))

- **deps**: Bump astral-sh/setup-uv from 4 to 6
  ([`d99499c`](https://github.com/SelfMemory/SelfMemory/commit/d99499ca4e9600e702b39de8c18b19a0af83f060))

- **deps**: Bump astral-sh/setup-uv from 6 to 7
  ([`c74b1c3`](https://github.com/SelfMemory/SelfMemory/commit/c74b1c3f97c2cbdaaa9c5521b73ba8720ad075bc))

### Documentation

- Add Home.md for project documentation
  ([`c5fde80`](https://github.com/SelfMemory/SelfMemory/commit/c5fde80c1128533d963b350d7aed2b245c95210e))

- Update Docusaurus configuration for SelfMemory site and add CNAME file
  ([`01bd50b`](https://github.com/SelfMemory/SelfMemory/commit/01bd50b4a996bb5421ba2b8cb301061705e1922a))

- Update README to include resources section; comment out unused configurations in code
  ([`b52e4b0`](https://github.com/SelfMemory/SelfMemory/commit/b52e4b09855f8563e1244828b383abe47b179549))

### Features

- Implement Weaviate vector store integration and enhance API authentication
  ([`0c9e7cd`](https://github.com/SelfMemory/SelfMemory/commit/0c9e7cdd834b09f036789cdebd7c43039c6aa310))


## v0.1.0 (2025-08-17)

- Initial Release
