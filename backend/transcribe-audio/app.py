import json
import os
from urllib.parse import urlparse

import boto3

# AWS clients
transcribe = boto3.client("transcribe")

def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse S3 URI into bucket and key."""
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3":
        raise ValueError("Not an S3 URI")
    return parsed.netloc, parsed.path.lstrip("/")

def get_media_format(key: str) -> str:
    """Get media format from file extension."""
    ext = key.rsplit(".", 1)[-1].lower()
    if ext not in ["mp3", "mp4", "wav", "flac", "ogg", "amr", "webm", "m4a"]:
        raise ValueError(f"Unsupported audio format: {ext}")
    return ext

def start_transcription(audio_uri: str, video_id: str) -> dict:
    """Start an AWS Transcribe job and return job details."""
    try:
        # Parse S3 URI and validate format
        bucket, key = parse_s3_uri(audio_uri)
        media_format = get_media_format(key)
        
        # Create unique job name
        job_name = f"transcribe-{video_id}"
        
        try:
            # Start new transcription job
            job = transcribe.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": audio_uri},
                MediaFormat=media_format,
                LanguageCode="en-US",
                Tags=[{"Key": "VideoId", "Value": video_id}],
            )["TranscriptionJob"]
        except transcribe.exceptions.ConflictException:
            # Job already exists, get its status
            job = transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )["TranscriptionJob"]
        
        return job
    except Exception as e:
        raise Exception(f"Failed to start transcription: {str(e)}")

def lambda_handler(event, context):
    """Entry point.
    
    Event example:
    {
        "s3_uri": "s3://bucket-name/video_id.m4a",
        "video_id": "dQw4w9WgXcQ"
    }
    """
    s3_uri = event.get("s3_uri")
    video_id = event.get("video_id")
    
    if not s3_uri or not video_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "s3_uri and video_id required"})
        }
    
    try:
        job = start_transcription(s3_uri, video_id)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Transcription job started",
                "job": {
                    "name": job["TranscriptionJobName"],
                    "status": job["TranscriptionJobStatus"],
                    "created": job["CreationTime"].isoformat(),
                    "video_id": video_id
                }
            })
        }
    except Exception as exc:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)})
        } 