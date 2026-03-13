import numpy as np
import pandas as pd
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re
import os
import tempfile

class MultimodalFuser:
    """
    Multimodal Fusion TextRank for Video Summarization.
    Fuses Transcript, Visual (Scene Changes), and Audio (Intensity/Emphasis).
    """
    
    def __init__(self):
        self.visual_weight = 0.35
        self.audio_weight = 0.25
        self.text_weight = 0.40
        self._ocr_reader = None

    def get_ocr_reader(self):
        """Lazy load EasyOCR reader."""
        if self._ocr_reader is None:
            try:
                import easyocr
                self._ocr_reader = easyocr.Reader(['en'])
            except Exception as e:
                print(f"Warning: EasyOCR failed to initialize: {e}")
        return self._ocr_reader

    def download_video_stream(self, video_url):
        """Downloads a low-resolution version of the video for analysis."""
        import yt_dlp
        temp_dir = tempfile.gettempdir()
        ydl_opts = {
            'format': 'best[height<=360][ext=mp4]/best[height<=360]/worst',
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        print(f"[*] Downloading video: {video_url} (360p)")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                if os.path.exists(filename):
                    print(f"[+] Download successful: {filename} ({os.path.getsize(filename)} bytes)")
                    return filename
                else:
                    print(f"[-] Download failed: File not found after yt-dlp run.")
                    return None
            except Exception as e:
                print(f"[-] yt-dlp error: {e}")
                return None

    def detect_scene_changes(self, video_path, threshold=0.3):
        """Detects scene changes using frame-to-frame histogram comparison."""
        print("[*] Detecting scene changes...")
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30 # Fallback
        
        scene_changes = []
        prev_hist = None
        
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Sample every 0.5 seconds to speed up
            if frame_idx % max(1, int(fps / 2)) != 0:
                frame_idx += 1
                continue
            
            # Convert to HSV and compute histogram
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            
            if prev_hist is not None:
                diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                if diff < (1 - threshold):
                    scene_changes.append(frame_idx / fps)
                    
            prev_hist = hist
            frame_idx += 1
            
        cap.release()
        return scene_changes

    def analyze_audio_intensity(self, video_path):
        """Analyzes audio energy (RMS) to find emphasis points."""
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(video_path)
            audio = clip.audio
            
            if audio is None:
                return np.array([0]), np.array([0])

            # Audio intensity over time
            duration = clip.duration
            fps = 2 # Sample energy twice per second
            times = np.arange(0, duration, 1/fps)
            intensities = []
            
            for t in times:
                try:
                    chunk = audio.subclip(t, min(t + 0.1, duration)).to_soundarray(fps=44100)
                    rms = np.sqrt(np.mean(chunk**2))
                    intensities.append(rms)
                except:
                    intensities.append(0)
                    
            intensities = np.array(intensities)
            # Normalize 0-100
            if intensities.size > 0 and intensities.max() > 0:
                intensities = (intensities / intensities.max()) * 100
            elif intensities.size > 0:
                intensities = np.zeros_like(intensities)
                
            clip.close()
            return times, intensities
        except ImportError:
            print("Warning: moviepy not installed. Audio intensity analysis skipped.")
            return np.array([0]), np.array([0])
        except Exception as e:
            print(f"Error analyzing audio: {e}")
            return np.array([0]), np.array([0])

    def perform_ocr_on_frame(self, video_path, timestamp):
        """Extracts text from a specific frame using OCR with preprocessing."""
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0: fps = 30
        
        text_samples = []
        # Sample the frame at t, t+0.5, and t+1.0 to find the clearest text
        for offset in [0, 0.5, 1.0]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((timestamp + offset) * fps))
            ret, frame = cap.read()
            if not ret:
                continue
                
            # Preprocess: Grayscale + Bilateral Filter (noise reduction while keeping edges)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            processed = cv2.bilateralFilter(gray, 9, 75, 75)
            
            reader = self.get_ocr_reader()
            if reader:
                try:
                    results = reader.readtext(processed)
                    sample_text = " ".join([res[1] for res in results if res[2] > 0.1]) # Filter by confidence
                    if sample_text:
                        text_samples.append(sample_text)
                except Exception as e:
                    print(f"OCR failed for frame at {timestamp + offset}: {e}")
            
            if not text_samples:
                # Fallback to pytesseract
                try:
                    import pytesseract
                    sample_text = pytesseract.image_to_string(processed)
                    if sample_text.strip():
                        text_samples.append(sample_text.strip())
                except:
                    pass
            
            # Short-circuit if we found good text (at least 20 chars)
            if text_samples and len(max(text_samples, key=len)) > 20:
                break
        
        cap.release()
        
        # Return the longest sample (likely the most complete extraction)
        if text_samples:
            return max(text_samples, key=len).strip()
        return ""

    def get_text_rank_scores(self, sentences):
        """Standard TextRank scoring for sentences."""
        if not sentences or len(sentences) < 2:
            return [100.0] * len(sentences) if sentences else []
            
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(sentences)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            nx_graph = nx.from_numpy_array(similarity_matrix)
            scores = nx.pagerank(nx_graph, max_iter=200)
            
            max_score = max(scores.values()) if scores else 1
            return [ (scores[i] / max_score) * 100 for i in range(len(sentences))]
        except Exception as e:
            print(f"TextRank calculation failed: {e}")
            return [50.0] * len(sentences)

    def fuse_multimodal_metrics(self, video_url, transcript_with_timestamps=None):
        """Main fusion logic."""
        # 1. Download and Analyze Video
        video_path = self.download_video_stream(video_url)
        if not video_path:
            return pd.DataFrame()

        scene_changes = self.detect_scene_changes(video_path)
        print(f"[+] Found {len(scene_changes)} scene changes.")
        
        audio_times, audio_intensities = self.analyze_audio_intensity(video_path)
        print(f"[*] Analyzing fusion results (Transcript present: {transcript_with_timestamps is not None})")
        
        # Fallback: if no scene changes found, sample every 30 seconds or based on audio peaks
        if not scene_changes:
            print("No scene changes detected. Using audio peaks and fixed intervals.")
            # Add audio peaks (top 5 by intensity)
            if audio_intensities.size > 0:
                peak_indices = np.argsort(audio_intensities)[-5:]
                scene_changes = [audio_times[idx] for idx in peak_indices]
            
            # Add fixed intervals every 60s
            duration = audio_times.max() if audio_times.size > 0 else 0
            for t in range(0, int(duration), 60):
                if t not in scene_changes:
                    scene_changes.append(float(t))
            
            scene_changes.sort()

        results = []
        
        if transcript_with_timestamps:
            sentences = [seg['text'] for seg in transcript_with_timestamps]
            text_scores = self.get_text_rank_scores(sentences)
            
            for i, seg in enumerate(transcript_with_timestamps):
                t_start = seg['start']
                vis_score = 0
                if any(abs(t_start - sc) < 2 for sc in scene_changes):
                    vis_score = 100
                
                audio_idx = np.abs(audio_times - t_start).argmin()
                aud_score = audio_intensities[audio_idx] if audio_idx < len(audio_intensities) else 0
                
                fused_score = (
                    self.text_weight * text_scores[i] +
                    self.visual_weight * vis_score +
                    self.audio_weight * aud_score
                )
                
                results.append({
                    'start': t_start,
                    'text': seg['text'],
                    'fused_score': min(100, fused_score),
                    'visual_score': vis_score,
                    'audio_score': aud_score,
                    'text_rank': text_scores[i]
                })
        else:
            # Case 2: NO transcripts (Visual + Audio)
            # 1. First, calculate preliminary fused scores for ALL candidates (no OCR yet)
            candidate_results = []
            for sc_time in scene_changes:
                audio_idx = np.abs(audio_times - sc_time).argmin()
                aud_score = audio_intensities[audio_idx] if audio_idx < len(audio_intensities) else 0
                vis_score = 100
                
                # Preliminary score based on visual/audio impact
                prelim_score = (0.6 * vis_score + 0.4 * aud_score)
                
                candidate_results.append({
                    'start': sc_time,
                    'visual_score': vis_score,
                    'audio_score': aud_score,
                    'prelim_score': prelim_score
                })
            
            # 2. Sort by prelim score and take Top 15 for deep OCR analysis
            candidate_results.sort(key=lambda x: x['prelim_score'], reverse=True)
            top_candidates = candidate_results[:15]
            
            # 3. Perform OCR on the cream of the crop
            print(f"[*] Performance Optimization: Running deep OCR on the top {len(top_candidates)} most significant moments...")
            for res in top_candidates:
                sc_time = res['start']
                ocr_text = self.perform_ocr_on_frame(video_path, sc_time)
                
                if ocr_text:
                    print(f"  [OCR @ {sc_time:.1f}s] Found: {ocr_text[:50]}...")
                
                t_score = 50 if ocr_text else 0
                fused_score = (
                    0.3 * t_score + 
                    0.5 * res['visual_score'] + 
                    0.2 * res['audio_score']
                )
                
                results.append({
                    'start': sc_time,
                    'text': ocr_text or f"Visual Highlight: Significant scene change or audio peak at {int(sc_time // 60):02d}:{int(sc_time % 60):02d}",
                    'fused_score': min(100, fused_score),
                    'visual_score': res['visual_score'],
                    'audio_score': res['audio_score'],
                    'text_rank': t_score
                })
        
        # Final safety check: if still empty (extremely rare), add a start point
        if not results:
            results.append({
                'start': 0, 'text': "Video Start", 'fused_score': 50,
                'visual_score': 50, 'audio_score': 50, 'text_rank': 0
            })
        
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except:
                pass
            
        return pd.DataFrame(results)

    def extract_multimodal_keyframes(self, video_url, transcript_with_timestamps=None, num_keyframes=5):
        """Extracts top keyframes based on multimodal fusion."""
        fused_df = self.fuse_multimodal_metrics(video_url, transcript_with_timestamps)
        
        if fused_df.empty:
            return [], pd.DataFrame()
            
        fused_df = fused_df.sort_values(by='fused_score', ascending=False)
        
        top_highlights = []
        seen_timestamps = []
        duration = fused_df['start'].max() if not fused_df.empty else 0
        
        for _, row in fused_df.iterrows():
            if any(abs(row['start'] - t) < (duration / (num_keyframes * 2)) for t in seen_timestamps):
                continue
                
            top_highlights.append({
                'timestamp': int(row['start']),
                'text': row['text'],
                'score': row['fused_score'],
                'metrics': {
                    'visual': row['visual_score'],
                    'audio': row['audio_score'],
                    'text': row['text_rank']
                }
            })
            seen_timestamps.append(row['start'])
            if len(top_highlights) >= num_keyframes:
                break
                
        top_highlights = sorted(top_highlights, key=lambda x: x['timestamp'])
        return top_highlights, fused_df

def get_multimodal_fusion_summary(video_url, transcript_with_timestamps=None, num_keyframes=7):
    """Utility function to be called from the main app."""
    from multimodal_fusion import MultimodalFuser
    fuser = MultimodalFuser()
    highlights, fused_df = fuser.extract_multimodal_keyframes(video_url, transcript_with_timestamps, num_keyframes)
    return highlights, fused_df

if __name__ == "__main__":
    pass
