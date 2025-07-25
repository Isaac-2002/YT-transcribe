import os
import json
import tempfile
from urllib.parse import urlparse, parse_qs

import boto3
import yt_dlp
import requests

# AWS clients
s3 = boto3.client("s3")

def extract_video_id(url: str) -> str:
    """Return the YouTube video ID from a standard or short URL."""
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com") and parsed.path == "/watch":
        return parse_qs(parsed.query)["v"][0]
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/")
    raise ValueError("Invalid YouTube URL")

def verify_public_video(video_id: str) -> bool:
    """Verify that the video exists and is publicly accessible."""
    # Using YouTube's oEmbed endpoint which only works for public videos
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}"
    response = requests.get(oembed_url)
    return response.status_code == 200

def download_audio(video_id: str, dest_dir: str) -> str:
    """Download the best audio stream as .m4a using yt-dlp and return the file path."""
    # First verify the video is public
    if not verify_public_video(video_id):
        raise ValueError("Video is not publicly accessible. Private, age-restricted, or members-only videos are not supported.")

    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(dest_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "outtmpl": output_template,
        # Basic options to help with reliability
        "no_warnings": True,
        "extract_flat": False,
        "max_downloads": 1,
        "retries": 3
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info.get('age_limit', 0) > 0:
                raise ValueError("Age-restricted videos are not supported")
            
    except Exception as e:
        print(f"Download error: {str(e)}")
        if "Private video" in str(e):
            raise ValueError("Private videos are not supported")
        elif "Sign in" in str(e):
            raise ValueError("This video requires authentication. Only public videos are supported.")
        else:
            raise Exception(f"Failed to download video: {str(e)}")

    # yt-dlp substitutes %(ext)s; find the created file
    for fname in os.listdir(dest_dir):
        if fname.startswith(video_id):
            return os.path.join(dest_dir, fname)
    raise FileNotFoundError("Audio download failed")

def upload_to_s3(file_path: str, bucket: str, key_prefix: str = "") -> str:
    """Upload file to S3 and return the s3 URI."""
    key = f"{key_prefix}{os.path.basename(file_path)}"
    s3.upload_file(file_path, bucket, key)
    return f"s3://{bucket}/{key}"

def create_response(status_code: int, body: dict) -> dict:
    """Create a response dictionary with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "http://yt-transcribe-frontend-dev-825765413106.s3-website.eu-west-2.amazonaws.com",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "POST,OPTIONS"
        },
        "body": json.dumps(body)
    }

def lambda_handler(event, context):
    """Entry point.
    
    Event example:
    { "youtube_url": "https://www.youtube.com/watch?v=..." }
    """
    # Handle OPTIONS request (CORS preflight)
    if event.get("httpMethod") == "OPTIONS":
        return create_response(200, {})

    try:
        # Parse body if it's a string
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            body = event.get("body", {})

        url = body.get("youtube_url")
        if not url:
            return create_response(400, {"error": "youtube_url required"})

        video_id = extract_video_id(url)
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = download_audio(video_id, tmpdir)
            bucket = os.environ["AUDIO_BUCKET"]
            s3_uri = upload_to_s3(audio_path, bucket)

        return create_response(200, {
            "message": "Audio uploaded successfully",
            "video_id": video_id,
            "s3_uri": s3_uri
        })
    except ValueError as ve:
        return create_response(400, {"error": str(ve)})
    except Exception as exc:
        print(f"Error processing request: {exc}")  # Add logging
        return create_response(500, {"error": str(exc)}) 