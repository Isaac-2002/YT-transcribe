# YT-Transcribe

A serverless application that downloads YouTube videos, transcribes them using AWS services, and provides summarized content.

## Architecture

- AWS Lambda for serverless processing
- AWS S3 for audio storage
- AWS Transcribe for speech-to-text
- AWS Comprehend/Bedrock for summarization

## Prerequisites

- Python 3.12.2
- AWS CLI configured
- AWS SAM CLI
- Node.js & npm (for frontend - coming soon)

## Local Development

1. Install AWS SAM CLI
2. Clone this repository
3. Follow setup instructions in each component directory

## Project Structure

```
.
├── backend/         # Python Lambda functions
├── frontend/        # Web UI (coming soon)
├── infrastructure/ # AWS SAM templates
└── .github/        # GitHub Actions workflows
```