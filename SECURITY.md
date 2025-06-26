# Security Guide

This document outlines the security measures implemented in the AI Task Assistant Bot and provides guidelines for secure deployment.

## 🔒 Security Features Implemented

### 1. **Input Validation**
- **Message Length Limits**: Messages are limited to 2000 characters to prevent DoS attacks
- **Content Filtering**: Basic filtering for suspicious patterns (script injection attempts)
- **Voice Duration Limits**: Voice messages limited to 120 seconds

### 2. **Rate Limiting**
- **Per-User Limits**: 30 requests per minute per user
- **Sliding Window**: 60-second sliding window for rate calculation
- **Automatic Blocking**: Users exceeding limits receive temporary blocks

### 3. **User Authorization** (Optional)
- **Whitelist Support**: Configure `ALLOWED_USERS` in `.env` to restrict access
- **User ID Validation**: Only authorized Telegram user IDs can use the bot

### 4. **File Security**
- **Path Traversal Protection**: Voice file names are sanitized to prevent directory traversal
- **Secure Cleanup**: Temporary files are cleaned up even if exceptions occur
- **Safe File Handling**: All file operations use secure path joining

### 5. **API Key Protection**
- **Environment Variables**: All sensitive credentials stored in `.env` files
- **No Hardcoding**: No API keys or tokens in source code
- **Secure Loading**: Credentials loaded securely at runtime

## 🛡️ Security Configuration

### Environment Variables
```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional Security Settings
ALLOWED_USERS=123456789,987654321  # Comma-separated user IDs
```

### File Permissions
```bash
chmod 600 .env  # Only owner can read/write
chmod 755 temp_audio/  # Temp directory permissions
```

## 🚨 Security Checklist

### Before Deployment
- [ ] `.env` file is not committed to Git
- [ ] API keys are valid and not exposed
- [ ] `ALLOWED_USERS` is configured if needed
- [ ] File permissions are set correctly
- [ ] Temporary directories exist and are writable

### Regular Maintenance
- [ ] Monitor rate limiting logs for abuse
- [ ] Rotate API keys periodically
- [ ] Review user access list
- [ ] Check for security updates in dependencies
- [ ] Monitor disk usage in temp directories

## 🔍 Security Monitoring

### Log Monitoring
The bot logs security-related events:
- Rate limit violations
- Authorization failures
- Input validation failures
- File operation errors

### Key Log Messages
```
WARNING - Rate limit exceeded for user 123456789
WARNING - Unauthorized access attempt from user 987654321
WARNING - Suspicious content detected in message
ERROR - Failed to cleanup file: path_traversal_attempt
```

## 🚀 Deployment Security

### Production Environment
1. **Use HTTPS**: Deploy behind a reverse proxy with SSL/TLS
2. **Firewall Rules**: Restrict network access to necessary ports only
3. **Process Isolation**: Run bot with minimal privileges
4. **Resource Limits**: Set memory and CPU limits
5. **Backup Strategy**: Secure backup of database and configuration

### Docker Deployment (Recommended)
```dockerfile
FROM python:3.11-slim
RUN useradd -m -u 1000 botuser
USER botuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "ai_assistant_bot.py"]
```

## 🔧 Incident Response

### If API Keys Are Compromised
1. **Immediate Actions**:
   - Revoke compromised keys immediately
   - Generate new API keys
   - Update `.env` file with new keys
   - Restart the bot

2. **Investigation**:
   - Check Git history: `git log --all --grep="API_KEY"`
   - Review access logs
   - Identify potential data exposure

3. **Prevention**:
   - Add keys to `.gitignore`
   - Use Git hooks to prevent commits with secrets
   - Consider using secret management services

### If Bot Is Compromised
1. **Stop the bot immediately**
2. **Review logs for suspicious activity**
3. **Check database for unauthorized changes**
4. **Rotate all credentials**
5. **Update and restart with security patches**

## 📞 Security Contacts

For security issues or questions:
- Review this documentation
- Check application logs
- Consult the project maintainer

## 🔄 Security Updates

This security guide should be reviewed and updated:
- When new features are added
- After security incidents
- During regular security audits
- When dependencies are updated

---

**Remember**: Security is an ongoing process, not a one-time setup. Regularly review and update your security measures.
