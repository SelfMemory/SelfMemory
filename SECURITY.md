# Security Policy

## Supported Versions

We take security seriously and will provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in InMemory, please report it to us in a responsible manner:

### How to Report

1. **Email**: Send details to `security@inmemory.dev`
2. **Subject**: Include "SECURITY" in the subject line
3. **Details**: Provide as much information as possible:
   - Description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact and attack scenarios
   - Any suggested fixes or mitigations

### What to Expect

- **Acknowledgment**: We will acknowledge receipt within 48 hours
- **Investigation**: We will investigate and assess the report within 5 business days
- **Updates**: We will provide regular updates on our progress
- **Resolution**: We aim to resolve critical issues within 30 days
- **Credit**: We will credit you in our security advisory (unless you prefer anonymity)

### Responsible Disclosure

We follow responsible disclosure principles:

1. **Grace Period**: We ask for 90 days to investigate and patch the issue
2. **Coordination**: We will work with you on the disclosure timeline
3. **Public Disclosure**: We will publish a security advisory after the fix is released
4. **CVE Assignment**: We will work with CVE coordinators for significant vulnerabilities

## Security Considerations

### Data Protection

InMemory handles sensitive memory data and implements several security measures:

**Encryption at Rest:**
- Memory content can be encrypted using AES-256
- User-specific encryption keys derived from secure sources
- Optional encryption for file storage backend

**Access Control:**
- User isolation in multi-user deployments
- API key authentication for managed services
- Role-based access control for enterprise features

**Network Security:**
- HTTPS-only communication for API endpoints
- Secure API key transmission
- CORS configuration for web applications

### Deployment Security

**File Storage Security:**
- Restricted file permissions (600) for data files
- Atomic write operations to prevent corruption
- Secure temporary file handling

**MongoDB Security:**
- Connection string encryption
- Database user authentication
- Collection-level isolation per user

**API Security:**
- Rate limiting on sensitive endpoints
- Input validation and sanitization
- Secure headers and CORS policies

### Configuration Security

**Secure Defaults:**
- No hardcoded credentials or API keys
- Secure random generation for API keys
- Environment variable configuration

**Configuration Validation:**
- Schema validation for all configuration
- Warnings for insecure configurations
- Automatic detection of credential exposure

## Security Best Practices

### For Users

**API Key Management:**
```python
# Good: Use environment variables
import os
api_key = os.getenv("INMEMORY_API_KEY")

# Bad: Hardcoded in source code
api_key = "im_12345..."  # Never do this
```

**Secure Configuration:**
```python
config = InMemoryConfig(
    storage={
        "type": "mongodb",
        "mongodb_uri": os.getenv("MONGODB_URI")  # From environment
    },
    auth={
        "type": "oauth",
        "google_client_secret": os.getenv("GOOGLE_CLIENT_SECRET")
    }
)
```

**File Permissions:**
```bash
# Ensure data directory is secure
chmod 700 ~/.inmemory/
chmod 600 ~/.inmemory/config.yaml
```

### For Developers

**Input Validation:**
- Always validate user input
- Use Pydantic models for request validation
- Sanitize data before storage

**Error Handling:**
- Don't expose sensitive information in error messages
- Log security events appropriately
- Use secure exception handling

**Testing:**
- Include security tests in test suite
- Test authentication and authorization
- Validate input sanitization

## Known Security Considerations

### Current Limitations

1. **Vector Database Security**: Qdrant security depends on deployment configuration
2. **Memory Content**: Stored in plaintext by default (encryption available but opt-in)
3. **API Logging**: May log sensitive information if debug logging is enabled
4. **File Storage**: Uses local filesystem permissions (not encrypted by default)

### Planned Improvements

- [ ] End-to-end encryption for all storage backends
- [ ] Audit logging for all security events
- [ ] Integration with external key management systems
- [ ] Advanced threat detection and monitoring
- [ ] Security compliance certifications (SOC 2, etc.)

## Security Updates

Security updates will be released as patch versions and announced through:

- **GitHub Security Advisories**
- **Release Notes**
- **Email notifications** (for registered users)
- **Community channels** (Discord, discussions)

## Compliance

InMemory is designed to help organizations meet various compliance requirements:

**GDPR (General Data Protection Regulation):**
- User data isolation and deletion capabilities
- Encryption options for personal data
- Audit logging for data access

**CCPA (California Consumer Privacy Act):**
- Data deletion and export capabilities
- User consent management features
- Transparency in data processing

**HIPAA (Healthcare):**
- Encryption capabilities for PHI
- Access logging and monitoring
- Secure configuration options

## Third-Party Security

We regularly monitor our dependencies for security vulnerabilities:

- **Automated Scanning**: GitHub Dependabot alerts
- **Security Audits**: Regular review of dependency security
- **Update Policy**: Prompt updates for security-related dependencies

### Key Dependencies Security

**Core Dependencies:**
- `qdrant-client`: Vector database client with security features
- `pydantic`: Data validation preventing injection attacks
- `cryptography`: Industry-standard cryptographic library
- `httpx`: Secure HTTP client with certificate validation

**Optional Dependencies:**
- `fastapi`: Modern Python web framework with security features
- `pymongo`: MongoDB client with authentication support
- `authlib`: OAuth and authentication library

## Contact

For security-related questions or concerns:

- **Security Email**: security@inmemory.dev
- **General Issues**: GitHub Issues (for non-security bugs)
- **Documentation**: See CONTRIBUTING.md for development security practices

## Acknowledgments

We appreciate the security research community and thank all researchers who responsibly disclose vulnerabilities to help keep InMemory secure.

---

**Last Updated**: January 17, 2025  
**Next Review**: April 17, 2025
