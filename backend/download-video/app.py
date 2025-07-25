import os
import json
import tempfile
from urllib.parse import urlparse, parse_qs

import boto3
import yt_dlp

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

def download_audio(video_id: str, dest_dir: str) -> str:
    """Download the best audio stream as .m4a using yt-dlp and return the file path."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(dest_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "outtmpl": output_template,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

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

def lambda_handler(event, context):
    """Entry point.
    
    Event example:
    { "youtube_url": "https://www.youtube.com/watch?v=..." }
    """
    url = event.get("youtube_url")
    if not url:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "youtube_url required"}),
        }

    try:
        video_id = extract_video_id(url)
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = download_audio(video_id, tmpdir)
            bucket = os.environ["AUDIO_BUCKET"]
            s3_uri = upload_to_s3(audio_path, bucket)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Audio uploaded successfully",
                "video_id": video_id,
                "s3_uri": s3_uri
            }),
        }
    except Exception as exc:
        return {"statusCode": 500, "body": json.dumps({"error": str(exc)})} 