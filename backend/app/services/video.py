import os
import subprocess
import re
import shutil
from typing import List, Dict, Optional, Tuple, Any
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from app.core.config import settings

class VideoService:
    @staticmethod
    def extract_youtube_id(url: str) -> Optional[str]:
        # Extracts YouTube ID from various URLs
        pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)([\w-]{11})'
        match = re.search(pattern, url)
        return match.group(1) if match else None

    @staticmethod
    def get_youtube_metadata(url: str) -> Dict[str, Any]:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "id": info.get("id"),
                    "title": info.get("title", "YouTube Video"),
                    "duration": info.get("duration", 0),
                    "view_count": info.get("view_count", 0),
                }
        except Exception as e:
            print(f"[Metadata] yt-dlp metadata extraction notice: {e}")
            vid_id = VideoService.extract_youtube_id(url)
            return {
                "id": vid_id,
                "title": f"YouTube Video ({vid_id})",
                "duration": 0,
                "view_count": 0,
            }

    @staticmethod
    def _parse_vtt_time(time_str: str) -> float:
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return 0.0

    @staticmethod
    def _parse_vtt(vtt_content: str) -> List[Dict[str, Any]]:
        from app.services.cleaner import cleaner_service
        raw_segments = []
        lines = vtt_content.splitlines()
        
        current_time_range = None
        current_text_lines = []
        time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3}|\d{2}:\d{2}\.\d{3})')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            time_match = time_pattern.search(line)
            if time_match:
                if current_time_range and current_text_lines:
                    text = " ".join(current_text_lines)
                    text = re.sub(r'<[^>]+>', '', text).strip()
                    if text:
                        start_sec = VideoService._parse_vtt_time(current_time_range[0])
                        end_sec = VideoService._parse_vtt_time(current_time_range[1])
                        raw_segments.append({
                            "text": text,
                            "start": start_sec,
                            "duration": max(1.0, end_sec - start_sec)
                        })
                current_time_range = (time_match.group(1), time_match.group(2))
                current_text_lines = []
            else:
                if current_time_range and not line.startswith("WEBVTT") and not line.startswith("NOTE"):
                    current_text_lines.append(line)
                    
        if current_time_range and current_text_lines:
            text = " ".join(current_text_lines)
            text = re.sub(r'<[^>]+>', '', text).strip()
            if text:
                start_sec = VideoService._parse_vtt_time(current_time_range[0])
                end_sec = VideoService._parse_vtt_time(current_time_range[1])
                raw_segments.append({
                    "text": text,
                    "start": start_sec,
                    "duration": max(1.0, end_sec - start_sec)
                })
                
        return cleaner_service.clean_transcript_segments(raw_segments)

    @staticmethod
    def _get_requests_session() -> Any:
        import requests
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Referer': 'https://www.youtube.com/',
        })
        return session

    @staticmethod
    def fetch_captions_via_api(video_id: str, session: Any) -> Optional[List[Dict[str, Any]]]:
        print(f"[Captions API] Checking youtube-transcript-api for video {video_id}...")
        try:
            from youtube_transcript_api._transcripts import TranscriptListFetcher
            fetcher = TranscriptListFetcher(session)
            transcript_list = fetcher.fetch(video_id)
            
            available_tracks = []
            for track in transcript_list:
                available_tracks.append(f"{track.language_code} (manual={not track.is_generated})")
            print(f"[Captions API] Available tracks: {', '.join(available_tracks)}")
            
            chosen_track = None
            
            # 1. Look for manual 'hi' or 'en'
            for track in transcript_list:
                if not track.is_generated and track.language_code in ('hi', 'en'):
                    chosen_track = track
                    break
            
            # 2. Look for any manual track
            if not chosen_track:
                for track in transcript_list:
                    if not track.is_generated:
                        chosen_track = track
                        break
            
            # 3. Look for auto-generated 'hi' or 'en'
            if not chosen_track:
                for track in transcript_list:
                    if track.is_generated and track.language_code in ('hi', 'en'):
                        chosen_track = track
                        break
            
            # 4. Fallback to first available
            if not chosen_track:
                for track in transcript_list:
                    chosen_track = track
                    break
                    
            if chosen_track:
                print(f"[Captions API] Selected track: {chosen_track.language_code} (manual={not chosen_track.is_generated})")
                data = chosen_track.fetch()
                return [{"text": entry["text"], "start": entry["start"], "duration": entry["duration"]} for entry in data]
            else:
                print("[Captions API] No subtitle tracks found in list response.")
        except Exception as e:
            print(f"[Captions API] Fetch failed: {e}")
        return None

    @staticmethod
    def fetch_captions_via_ytdlp(video_id: str, session: Any) -> Optional[List[Dict[str, Any]]]:
        print(f"[Captions yt-dlp] Checking yt-dlp metadata for video {video_id}...")
        url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'format': 'best',
            'ignore_no_formats_error': True,
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios']
                }
            }
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            subtitles = info.get('subtitles') or {}
            automatic_captions = info.get('automatic_captions') or {}

            manual_langs = list(subtitles.keys())
            auto_langs = list(automatic_captions.keys())
            print(f"[Captions yt-dlp] Available manual subtitles: {manual_langs}")
            print(f"[Captions yt-dlp] Available auto-generated captions: {auto_langs}")

            chosen_lang = None
            is_manual = False

            # 1. Manual 'en' or 'hi'
            for lang in ('en', 'hi'):
                if lang in subtitles:
                    chosen_lang = lang
                    is_manual = True
                    break

            # 2. Any manual
            if not chosen_lang and manual_langs:
                chosen_lang = manual_langs[0]
                is_manual = True

            # 3. Auto 'en' or 'hi'
            if not chosen_lang:
                for lang in ('en', 'hi'):
                    if lang in automatic_captions:
                        chosen_lang = lang
                        is_manual = False
                        break

            # 4. Any auto
            if not chosen_lang and auto_langs:
                chosen_lang = auto_langs[0]
                is_manual = False

            if not chosen_lang:
                print("[Captions yt-dlp] No subtitle tracks found in yt-dlp metadata.")
                return None

            print(f"[Captions yt-dlp] Selected language: {chosen_lang} (manual={is_manual})")

            track_formats = subtitles[chosen_lang] if is_manual else automatic_captions[chosen_lang]

            vtt_format = None
            for fmt in track_formats:
                if fmt.get('ext') == 'vtt':
                    vtt_format = fmt
                    break
            if not vtt_format and track_formats:
                vtt_format = track_formats[0]

            if not vtt_format or not vtt_format.get('url'):
                print(f"[Captions yt-dlp] No valid subtitle URLs found for language {chosen_lang}.")
                return None

            sub_url = vtt_format['url']
            print(f"[Captions yt-dlp] Fetching subtitle via yt-dlp urlopen: {sub_url[:80]}...")

            # Use yt-dlp's own internal HTTP handler to bypass YouTube 429 blocks
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                response = ydl.urlopen(sub_url)
                vtt_content = response.read().decode('utf-8')

            print(f"[Captions yt-dlp] Successfully fetched {len(vtt_content)} bytes of subtitle content.")
            return VideoService._parse_vtt(vtt_content)
        except Exception as e:
            print(f"[Captions yt-dlp] Fetch failed: {e}")
        return None


    @staticmethod
    def fetch_youtube_captions(video_id: str) -> Optional[List[Dict[str, Any]]]:
        session = VideoService._get_requests_session()
        
        # 1. API fetch
        captions = VideoService.fetch_captions_via_api(video_id, session)
        if captions:
            print("[Captions Orchestrator] Successfully retrieved captions via youtube-transcript-api.")
            return captions
            
        print("[Captions Orchestrator] API retrieval failed. Falling back to yt-dlp metadata extraction...")
        
        # 2. yt-dlp fetch
        captions = VideoService.fetch_captions_via_ytdlp(video_id, session)
        if captions:
            print("[Captions Orchestrator] Successfully retrieved captions via yt-dlp metadata.")
            return captions
            
        print("[Captions Orchestrator] Both pre-existing caption sources failed. Fallback to Whisper will be triggered.")
        return None

    @staticmethod
    def download_youtube_video(url: str, output_path: str) -> str:
        # Download fast lightweight 480p stream for ultra-fast slide extraction
        ydl_opts = {
            'format': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return output_path

    @staticmethod
    def download_youtube_audio(url: str, output_path: str) -> str:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # yt-dlp appends .mp3 extension if downloaded successfully
        real_path = output_path if output_path.endswith(".mp3") else f"{os.path.splitext(output_path)[0]}.mp3"
        return real_path

    @staticmethod
    def extract_audio_from_video(video_path: str, audio_output_path: str) -> str:
        # Runs FFmpeg command to extract audio as mp3
        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            audio_output_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")
        return audio_output_path

    @staticmethod
    def extract_keyframes(video_path: str, output_dir: str, interval_seconds: int = 30) -> List[Tuple[float, str]]:
        """
        Extracts keyframes from a video file every interval_seconds (default: 30s).
        Returns a list of tuples containing (timestamp_in_seconds, local_image_path).
        """
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        keyframes_list = []
        
        # 1. Try FFmpeg first
        output_pattern = os.path.join(output_dir, "frame_%04d.jpg")
        command = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"fps=1/{interval_seconds}",
            "-vsync", "vfr",
            output_pattern
        ]
        
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                files = sorted([f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")])
                for idx, fname in enumerate(files):
                    timestamp = float(idx * interval_seconds)
                    keyframes_list.append((timestamp, os.path.join(output_dir, fname)))
                if keyframes_list:
                    print(f"[Keyframe Extraction] Extracted {len(keyframes_list)} frames via FFmpeg.")
                    return keyframes_list
        except Exception as e:
            print(f"[Keyframe FFmpeg notice]: {e}")

        # 2. Fallback to OpenCV (cv2)
        try:
            import cv2
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_interval = int(fps * interval_seconds)
                count = 0
                frame_idx = 0
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if count % max(1, frame_interval) == 0:
                        timestamp = float(count / fps)
                        fname = f"frame_{frame_idx:04d}.jpg"
                        fpath = os.path.join(output_dir, fname)
                        cv2.imwrite(fpath, frame)
                        keyframes_list.append((timestamp, fpath))
                        frame_idx += 1
                    count += 1
                cap.release()
        except Exception as cv_err:
            print(f"[Keyframe OpenCV notice]: {cv_err}")

        from app.services.cleaner import cleaner_service
        raw_count = len(keyframes_list)
        deduped_list = cleaner_service.deduplicate_keyframes(keyframes_list)
        print(f"[Keyframe Deduplication] Filtered redundant static slides: {raw_count} raw frames -> {len(deduped_list)} unique keyframe slides.")
        return deduped_list

    @staticmethod
    def get_video_duration(file_path: str) -> float:
        command = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except ValueError:
                return 0.0
        return 0.0

video_service = VideoService()
