import os
import streamlit as st
import requests
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from urllib.parse import urlparse, parse_qs
from urllib.parse import urlparse, parse_qs
import re
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import uuid
from datetime import datetime
import google.generativeai as genai
from youtubesearchpython import VideosSearch

# NLP and ML imports for TextRank and PCA
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import PCA
import networkx as nx
import pandas as pd
from engagement_fusion import get_engagement_fusion_summary
from multimodal_fusion import get_multimodal_fusion_summary

# NLTK imports with better error handling
import shutil
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')


def setup_nltk():
    """Setup NLTK data with proper error handling"""
    try:
        # Clear any corrupted NLTK data first
        nltk_data_dir = os.path.join(os.path.expanduser('~'), 'nltk_data')
        
        # Try to import sentence tokenizer
        try:
            from nltk.tokenize import sent_tokenize
            from nltk.corpus import stopwords
            # Test if they work
            sent_tokenize("Test sentence.")
            return True
        except (LookupError, ImportError, OSError):
            pass
        
        # Download required data
        print("Downloading NLTK data...")
        
        # Download punkt tokenizer
        try:
            nltk.download('punkt', quiet=False, raise_on_error=True)
        except Exception as e:
            print(f"Error downloading punkt: {e}")
            # Try alternative download method
            nltk.download('punkt', quiet=False)
        
        # Download stopwords
        try:
            nltk.download('stopwords', quiet=False, raise_on_error=True)
        except Exception as e:
            print(f"Error downloading stopwords: {e}")
            nltk.download('stopwords', quiet=False)
        
        # Verify downloads
        from nltk.tokenize import sent_tokenize
        sent_tokenize("Test sentence.")
        
        return True
        
    except Exception as e:
        print(f"NLTK setup error: {e}")
        st.error(f"⚠️ NLTK setup failed: {e}")
        st.info("💡 Try running: python -m nltk.downloader punkt stopwords")
        return False

# Setup NLTK (do this before importing tokenizers)
nltk_ready = setup_nltk()

if nltk_ready:
    from nltk.tokenize import sent_tokenize
    try:
        from nltk.corpus import stopwords
        STOP_WORDS = set(stopwords.words('english'))
    except:
        STOP_WORDS = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'])
else:
    # Fallback tokenizer if NLTK fails
    def sent_tokenize(text):
        """Simple sentence tokenizer fallback"""
        import re
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    STOP_WORDS = set(['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                      'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had'])

# Load environment variables
load_dotenv()

# Neon Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Configure Google Generative AI with API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# Use Gemini Flash Latest (Stable Alias)
# Use Gemini Flash Latest (Stable Alias)
MODEL_NAME = "gemini-flash-latest"

def call_gemini_safe(prompt, max_retries=4, base_delay=10):
    """
    Call Gemini API with retry logic for rate limits (429)
    """
    import time
    for attempt in range(max_retries):
        try:
            if not GOOGLE_API_KEY:
                st.error("❌ Google API Key not configured. Please check your .env file.")
                return None
            
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait_time = base_delay * (2 ** attempt)
                st.warning(f"⏳ Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                st.error(f"❌ Gemini API Error: {e}")
                return None
                
    st.error("❌ API Quota Exceeded. Please try again later.")
    return None

# Prompt for Gemini AI
gemini_prompt = """
Create detailed notes from this YouTube video transcript with the following structure:

1. Extract 5-7 KEY FRAMES (main topic shifts or important moments) from the video, and identify an approximate timestamp for each keyframe.
2. For each keyframe:
   - Begin with "## KEYFRAME [timestamp]: [Brief title of the keyframe]"
   - The timestamp should be in the format MM:SS or HH:MM:SS depending on video length
   - Follow with a detailed explanation of the content related to this keyframe
   - Include any important quotes, facts, or insights from this section
   - Format supporting points as bullet lists

Focus on providing comprehensive notes that capture the essential content while maintaining the logical flow of the video. Ensure the keyframes together provide a complete understanding of the video content.
"""

# --------- Authentication Functions ---------

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    """Initialize database table for users"""
    try:
        if not DATABASE_URL:
            return False
            
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS user_history (
                id SERIAL PRIMARY KEY,
                user_id UUID REFERENCES users(id),
                video_url TEXT NOT NULL,
                video_title TEXT,
                summary TEXT,
                transcript TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error initializing database: {str(e)}")
        return False

def register_user(username, password, email):
    """Register a new user in Neon database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(password)
        
        cur.execute(
            "INSERT INTO users (id, username, password, email) VALUES (%s, %s, %s, %s)",
            (user_id, username, hashed_password, email)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return True, "Registration successful!"
    except Exception as e:
        return False, f"Registration failed: {str(e)}"

def authenticate_user(username, password):
    """Authenticate user against Neon database"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        hashed_password = hash_password(password)
        
        cur.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s",
            (username, hashed_password)
        )
        
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        
        if user_data:
            return True, dict(user_data)
        return False, None
    except Exception as e:
        st.error(f"Authentication error: {str(e)}")
        return False, None

def check_username_exists(username):
    """Check if username already exists"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        exists = cur.fetchone() is not None
        
        cur.close()
        conn.close()
        return exists
    except Exception as e:
        st.error(f"Error checking username: {str(e)}")
        return False

def save_history(user_id, video_url, video_title, summary, transcript):
    """Save summarization history to database"""
    try:
        if not DATABASE_URL:
            return False
            
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if URL already exists for this user to avoid duplicates (optional, but good for history)
        # For now, we'll just insert a new record each time or you could update. 
        # let's just insert to keep a log of all actions.
        
        cur.execute(
            """
            INSERT INTO user_history (user_id, video_url, video_title, summary, transcript)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (user_id, video_url, video_title, summary, transcript)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving history: {e}")
        return False

def get_user_history(user_id):
    """Retrieve history for a user"""
    try:
        if not DATABASE_URL:
            return []
            
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            """
            SELECT * FROM user_history 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,)
        )
        
        history = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert RealDictRow to list of dicts
        return [dict(row) for row in history]
    except Exception as e:
        st.error(f"Error retrieving history: {str(e)}")
        return []

def get_related_videos_from_history(current_video_id, current_transcript, user_id):
    """
    Find related videos from user history using TF-IDF and Cosine Similarity
    """
    try:
        # Get user history
        history = get_user_history(user_id)
        if not history or len(history) < 2:
            return []
            
        # Filter out current video
        other_videos = [h for h in history if extract_video_id(h['video_url']) != current_video_id]
        
        if not other_videos:
            return []
            
        # Prepare corpus for TF-IDF
        corpus = [v['transcript'] for v in other_videos]
        corpus.append(current_transcript)
        
        # Calculate TF-IDF
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # Calculate cosine similarity of current video (last in corpus) with all others
        cosine_sim = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
        
        # Get top 3 related videos
        related_indices = cosine_sim[0].argsort()[-3:][::-1]
        
        related_videos = []
        for idx in related_indices:
            score = cosine_sim[0][idx]
            if score > 0.1:  # Filter low similarity
                video = other_videos[idx]
                video['similarity_score'] = score
                related_videos.append(video)
                
        return related_videos
        
    except Exception as e:
        print(f"Error getting related videos: {e}")
        return []


@st.cache_data(show_spinner=False)
def analyze_video_metadata(transcript_text):
    """
    Get both Category and Related Topics in ONE call to save quota.
    """
    try:
        prompt = """
        Analyze the following video transcript and provide:
        1. The broad category (Choose ONE: Technology, Education, Entertainment, Music, Gaming, News, Sports, Cooking, Travel, Health, Motivation, Business).
        2. A list of 5 specific, interesting related topics/search queries.
        
        Format the output EXACTLY like this:
        CATEGORY: [Category Name]
        TOPICS:
        - [Topic 1]
        - [Topic 2]
        ...
        
        Transcript:
        """ + transcript_text[:10000]
        
        response_text = call_gemini_safe(prompt)
        if not response_text:
            return "General", []
            
        # Parse output
        category = "General"
        topics = []
        
        lines = response_text.strip().split('\n')
        for line in lines:
            if line.startswith("CATEGORY:"):
                category = line.replace("CATEGORY:", "").strip()
            elif line.strip().startswith("-"):
                topic = line.replace("-", "").strip()
                if topic:
                    topics.append(topic)
                    
        return category, topics[:5]
        
    except Exception as e:
        print(f"Metadata analysis failed: {e}")
        return "General", []

def get_youtube_search_results(query, max_results=5):
    """
    Search YouTube and return video details (title, link, thumbnail, views, publishedTime)
    """
    try:
        videos_search = VideosSearch(query, limit=max_results)
        results = videos_search.result()
        
        videos = []
        for item in results['result']:
            try:
                video_info = {
                    'title': item['title'],
                    'link': item['link'],
                    'thumbnail': item['thumbnails'][0]['url'],
                    'views': item.get('viewCount', {}).get('short', 'N/A views'),
                    'published': item.get('publishedTime', 'Unknown date'),
                    'duration': item.get('duration', '')
                }
                videos.append(video_info)
            except:
                continue
                
        return videos
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        return []

def ask_about_video(transcript_text, question):
    """
    Answer user questions based on the transcript
    """
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        You are a helpful assistant analyzing a video transcript.
        Answer the user's question based STRICTLY on the content provided below.
        Keep your answer CONCISE and to the point (maximum 3-4 sentences).
        If the answer is not in the transcript, politicial state that the video does not cover that topic.
        
        Question: {question}
        
        Transcript:
        {transcript_text[:15000]}
        """
        
        return call_gemini_safe(prompt)
    except Exception as e:
        return f"Sorry, I couldn't process that question: {e}"

# --------- TextRank Algorithm Implementation ---------

def preprocess_text(text):
    """Clean and preprocess text for TextRank while maintaining basic structure"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Be more selective about character removal to avoid losing meaning
    # Keep alphanumeric, common punctuation, and spaces
    text = re.sub(r'[^\w\s.,!?;:\'\"-]', '', text)
    return text.strip()

def textrank_summarize(text, num_sentences=10, use_pca=True, pca_components=50, min_words=None):
    """
    Implement TextRank algorithm for extractive summarization
    
    Args:
        text: Input text to summarize
        num_sentences: Number of sentences to extract
        use_pca: Whether to apply PCA for dimensionality reduction
        pca_components: Number of PCA components to keep
        min_words: Minimum word count for the summary (optional)
    
    Returns:
        Summary text with top-ranked sentences
    """
    try:
        # Preprocess text
        clean_text = preprocess_text(text)
        
        # Tokenize into sentences
        sentences = sent_tokenize(clean_text)
        
        if len(sentences) < num_sentences:
            return clean_text  # Return original if too short
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=1000,
            ngram_range=(1, 2)
        )
        
        try:
            sentence_vectors = vectorizer.fit_transform(sentences)
        except ValueError:
            # If TF-IDF fails, return first sentences
            return ' '.join(sentences[:num_sentences])
        
        # Apply PCA for dimensionality reduction if requested
        if use_pca and sentence_vectors.shape[1] > pca_components:
            pca = PCA(n_components=min(pca_components, sentence_vectors.shape[0], sentence_vectors.shape[1]))
            sentence_vectors_reduced = pca.fit_transform(sentence_vectors.toarray())
            
            # Calculate explained variance
            explained_variance = sum(pca.explained_variance_ratio_)
            
            # Log PCA info
            try:
                st.sidebar.info(f"🔍 PCA Applied: {pca_components} components retain {explained_variance*100:.1f}% variance")
            except:
                pass
        else:
            sentence_vectors_reduced = sentence_vectors.toarray()
        
        # Calculate cosine similarity matrix
        similarity_matrix = cosine_similarity(sentence_vectors_reduced)
        
        # Build graph from similarity matrix
        nx_graph = nx.from_numpy_array(similarity_matrix)
        
        # Apply PageRank algorithm (TextRank)
        try:
            # Try with strict tolerance and high iterations
            scores = nx.pagerank(nx_graph, max_iter=10000, tol=1e-06)
        except nx.PowerIterationFailedConvergence:
            try:
                # Fallback 1: Relaxed tolerance
                scores = nx.pagerank(nx_graph, max_iter=10000, tol=1e-04)
            except (nx.PowerIterationFailedConvergence, Exception):
                # Fallback 2: Degree Centrality (sum of edge weights)
                # This is a robust alternative when PageRank fails to converge
                scores = dict(nx_graph.degree(weight='weight'))
                
                # If graph is somehow disconnected or empty, fallback to simple position scoring
                if not scores and sentences:
                     scores = {i: 1.0 for i in range(len(sentences))}

        
        # Rank sentences by score
        ranked_sentences = sorted(
            ((scores[i], i, sentence) for i, sentence in enumerate(sentences)),
            reverse=True
        )
        
        # Select top sentences
        # If min_words is set, we might need more than num_sentences
        selected_indices = []
        current_word_count = 0
        
        for i in range(len(ranked_sentences)):
            _, idx, sentence = ranked_sentences[i]
            selected_indices.append(idx)
            current_word_count += len(sentence.split())
            
            # Stop if we have enough sentences AND meet min_words (if specified)
            if len(selected_indices) >= num_sentences:
                if min_words is None or current_word_count >= min_words:
                    break
        
        # Sort selected indices to maintain original order
        selected_indices.sort()
        summary_sentences = [sentences[idx] for idx in selected_indices]
        
        # Combine selected sentences
        summary = ' '.join(summary_sentences)
        
        # Ensure it ends with proper punctuation
        if summary and summary[-1] not in '.!?':
            summary += '...'
        
        return summary
        
    except Exception as e:
        st.error(f"Error in TextRank summarization: {str(e)}")
        return text[:1000]  # Fallback to truncation

def refine_textrank_summary(raw_summary):
    """
    Refine raw TextRank output using Gemini for better grammar and structure.
    """
    if not raw_summary or len(raw_summary.split()) < 10:
        return raw_summary
        
    try:
        refine_prompt = f"""
        Refine the following extractive summary into a professional, grammatically correct, and well-structured summary.
        
        RULES:
        1. Fix any grammar, punctuation, or capitalization issues.
        2. Maintain all key facts and insights from the original text.
        3. If the content is long, use bullet points for clarity.
        4. Ensure a smooth, logical flow between ideas.
        5. Keep the response concise but comprehensive.
        6. Do NOT add information not present in the original text.
        7. Output ONLY the refined text.
        
        Original Text:
        {raw_summary}
        
        Refined Summary:
        """
        
        refined_text = call_gemini_safe(refine_prompt)
        return refined_text if refined_text else raw_summary
    except Exception as e:
        print(f"Refinement error: {e}")
        return raw_summary

def extract_keyframes_with_textrank(transcript_with_timestamps, num_keyframes=7):
    """
    Extract keyframes using TextRank algorithm
    
    Args:
        transcript_with_timestamps: List of transcript segments with timestamps
        num_keyframes: Number of keyframes to extract
    
    Returns:
        List of keyframes with timestamps and summaries
    """
    try:
        if not transcript_with_timestamps:
            return []
        
        # Calculate total duration
        total_duration = (
            transcript_with_timestamps[-1]["start"] +
            transcript_with_timestamps[-1]["duration"]
        )
        
        # Divide into segments
        segment_duration = total_duration / num_keyframes
        keyframes = []
        
        for i in range(num_keyframes):
            segment_start = i * segment_duration
            segment_end = (i + 1) * segment_duration
            
            # Get transcript segments in this time range
            segment_texts = []
            for entry in transcript_with_timestamps:
                if segment_start <= entry["start"] < segment_end:
                    segment_texts.append(entry["text"])
            
            if segment_texts:
                segment_text = " ".join(segment_texts)
                
                # Calculate dynamic sentence count based on segment length
                word_count = len(segment_text.split())
                # Aim for ~1 sentence per 100 words, min 3, max 8
                segment_num_sentences = max(3, min(8, int(word_count / 100) + 2))
                
                # Apply TextRank to extract key sentences from this segment
                # Also set a min_words target for more substantial summaries
                raw_summary = textrank_summarize(
                    segment_text, 
                    num_sentences=segment_num_sentences, 
                    use_pca=True,
                    min_words=50 # Target at least 50 words for a "long keyframe"
                )
                
                # Refine the summary using Gemini for better quality
                summary = refine_textrank_summary(raw_summary)
                
                # Calculate timestamp
                timestamp_seconds = int(segment_start + segment_duration / 2)
                
                keyframes.append({
                    'timestamp': timestamp_seconds,
                    'timestamp_str': format_timestamp(timestamp_seconds),
                    'summary': summary,
                    'title': f"Segment {i+1}"
                })
        
        return keyframes
        
    except Exception as e:
        st.error(f"Error extracting keyframes with TextRank: {str(e)}")
        return []

def apply_pca_to_transcript(transcript_text, n_components=100):
    """
    Apply PCA to transcript for dimensionality reduction and feature extraction
    
    Args:
        transcript_text: Full transcript text
        n_components: Number of principal components to extract
    
    Returns:
        PCA analysis results and explained variance
    """
    try:
        # Tokenize into sentences
        sentences = sent_tokenize(transcript_text)
        
        if len(sentences) < 10:
            return None, "Transcript too short for PCA analysis"
        
        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer(
            stop_words='english',
            max_features=500,
            ngram_range=(1, 2)
        )
        
        sentence_vectors = vectorizer.fit_transform(sentences).toarray()
        
        # Apply PCA
        n_components = min(n_components, sentence_vectors.shape[0], sentence_vectors.shape[1])
        pca = PCA(n_components=n_components)
        
        reduced_vectors = pca.fit_transform(sentence_vectors)
        
        # Get explained variance
        explained_variance = pca.explained_variance_ratio_
        cumulative_variance = np.cumsum(explained_variance)
        
        # Find optimal number of components (95% variance)
        optimal_components = np.argmax(cumulative_variance >= 0.95) + 1
        
        pca_results = {
            'n_components': n_components,
            'optimal_components': optimal_components,
            'explained_variance': explained_variance,
            'cumulative_variance': cumulative_variance,
            'reduced_vectors': reduced_vectors,
            'total_variance_95': cumulative_variance[min(optimal_components-1, len(cumulative_variance)-1)]
        }
        
        return pca_results, None
        
    except Exception as e:
        return None, f"PCA analysis failed: {str(e)}"

# --------- Translation Functions ---------

@st.cache_data(show_spinner=False)
def translate_text(text, target_language):
    """
    Translate text to target language using Gemini
    
    Args:
        text (str): Text to translate
        target_language (str): Target language (e.g., "Telugu", "Hindi")
        
    Returns:
        str: Translated text
    """
    if not text or target_language == "English":
        return text
        
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        Translate the following text to {target_language}.
        Maintain the original markdown formatting, including headers (start with ##), bullet points, and bold text.
        Do not explain the translation, just provide the translated content.
        
        Text to translate:
        {text}
        """
        
        response = call_gemini_safe(prompt)
        return response if response else text
    except Exception as e:
        st.error(f"Translation failed: {str(e)}")
        return text

# --------- Gemini AI Functions ---------

@st.cache_data(show_spinner=False)
def generate_gemini_content(transcript_text, prompt, target_language="English"):
    try:
        full_prompt = prompt + "\n\nTranscript:\n" + transcript_text
        
        if target_language != "English":
            full_prompt += f"\n\nIMPORTANT: Provide the response in {target_language} language."
        
        return call_gemini_safe(full_prompt)
        
    except Exception as e:
        st.error(f"❌ Error generating content with Gemini AI: {str(e)}")
        return None

# --------- YouTube Functions ---------

def extract_video_id(youtube_video_url):
    try:
        parsed_url = urlparse(youtube_video_url)

        # Handle various YouTube domains
        valid_domains = ["www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com"]
        
        if parsed_url.netloc in ["youtu.be"]:
            return parsed_url.path[1:]
        elif parsed_url.netloc in valid_domains:
            if "shorts" in parsed_url.path:
                # Handle YouTube Shorts URLs
                return parsed_url.path.split("/")[-1]
            if "v" in parse_qs(parsed_url.query):
                return parse_qs(parsed_url.query)["v"][0]
            # Handle live streams or other formats
            if parsed_url.path.startswith("/live/"):
                return parsed_url.path.split("/")[-1]
            return None
        else:
            raise ValueError("Invalid YouTube URL format")

    except Exception:
        st.error("❌ Invalid YouTube link! Please enter a valid YouTube video URL.")
        return None

def get_video_title(video_url):
    """Get video title using OEmbed"""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={video_url}&format=json"
        response = requests.get(oembed_url)
        if response.status_code == 200:
            return response.json().get('title', 'Unknown Video')
        return "Unknown Video"
    except Exception:
        return "Unknown Video"

@st.cache_data(show_spinner=False)
def extract_transcript_details(youtube_video_url):
    try:
        video_id = extract_video_id(youtube_video_url)
        if not video_id:
            return None, None

        ytt_api = YouTubeTranscriptApi()
        fetched = ytt_api.fetch(video_id)
        transcript_list = fetched.to_raw_data()

        transcript_with_timestamps = transcript_list
        transcript_text = " ".join(entry["text"] for entry in transcript_list)

        return transcript_text, transcript_with_timestamps

    except TranscriptsDisabled:
        st.error("❌ Transcripts are disabled for this video.")
        return None, None
    except NoTranscriptFound:
        st.error("❌ No transcript found for this video.")
        return None, None
    except Exception as e:
        st.error(f"❌ Error retrieving transcript: {str(e)}")
        return None, None

def extract_timestamps_from_notes(keyframe_notes):
    pattern = r"## KEYFRAME \[([0-9:]+)\]:"
    timestamps = re.findall(pattern, keyframe_notes)

    seconds_list = []
    for ts in timestamps:
        parts = ts.split(":")
        if len(parts) == 2:
            seconds = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            seconds = 0
        seconds_list.append(seconds)

    return seconds_list

def format_timestamp(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def estimate_keyframe_timestamps(transcript_with_timestamps, num_keyframes=5):
    if not transcript_with_timestamps:
        return []

    video_duration = (
        transcript_with_timestamps[-1]["start"]
        + transcript_with_timestamps[-1]["duration"]
    )
    segment_duration = video_duration / num_keyframes

    timestamps = []
    for i in range(num_keyframes):
        timestamp = int((i + 0.5) * segment_duration)
        timestamps.append(timestamp)

    return timestamps

def get_diverse_thumbnails(video_id, num_thumbnails):
    thumbnails = []
    quality_options = ["default", "mqdefault", "hqdefault", "sddefault"]

    for i in range(num_thumbnails):
        quality = quality_options[i % len(quality_options)]
        thumbnail_url = (
            f"https://img.youtube.com/vi/{video_id}/{quality}.jpg?index={i}&cb={i}"
        )
        thumbnails.append(thumbnail_url)

    return thumbnails

def display_keyframe_notes_with_thumbnails(keyframe_notes, video_id, timestamps):
    try:
        thumbnails = get_diverse_thumbnails(video_id, len(timestamps))

        pattern = r"## KEYFRAME \[([0-9:]+)\]: (.*?)\n(.*?)(?=## KEYFRAME|\Z)"
        matches = re.findall(pattern, keyframe_notes, re.DOTALL)

        if not matches:
            st.markdown(keyframe_notes)
            return

        for i, (timestamp_str, title, content) in enumerate(matches):
            with st.container():
                st.markdown(f"## KEYFRAME [{timestamp_str}]: {title}")

                parts = timestamp_str.split(":")
                ts_seconds = 0
                if len(parts) == 2:
                    ts_seconds = int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    ts_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                col1, col2 = st.columns([1, 2])

                with col1:
                    if i < len(thumbnails):
                        st.image(thumbnails[i], caption=f"Keyframe at {timestamp_str}")
                    st.markdown(
                        f"[▶️ Watch this section on YouTube](https://www.youtube.com/watch?v={video_id}&t={ts_seconds})"
                    )

                with col2:
                    st.markdown(content)

                st.markdown("---")
    except Exception as e:
        st.error(f"Error displaying notes: {str(e)}")
        st.markdown(keyframe_notes)

def generate_markdown_with_thumbnails(keyframe_notes, video_id, timestamps):
    try:
        thumbnails = get_diverse_thumbnails(video_id, len(timestamps))

        pattern = r"(## KEYFRAME \[([0-9:]+)\]: (.*?)\n)(.*?)(?=## KEYFRAME|\Z)"
        matches = re.findall(pattern, keyframe_notes, re.DOTALL)

        if not matches:
            return keyframe_notes

        enhanced = ""

        for i, (header, timestamp_str, title, content) in enumerate(matches):
            parts = timestamp_str.split(":")
            ts_seconds = 0
            if len(parts) == 2:
                ts_seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                ts_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

            enhanced += header

            if i < len(thumbnails):
                thumbnail_url = thumbnails[i]
                youtube_link = f"https://www.youtube.com/watch?v={video_id}&t={ts_seconds}"
                enhanced += f"![Keyframe at {timestamp_str}]({thumbnail_url})\n\n"
                enhanced += f"[▶️ Watch this section on YouTube]({youtube_link})\n\n"

            enhanced += content

        return enhanced

    except Exception:
        return keyframe_notes

def format_textrank_keyframes(keyframes, video_id):
    markdown = ""
    thumbnails = get_diverse_thumbnails(video_id, len(keyframes))
    
    for i, kf in enumerate(keyframes):
        markdown += f"## KEYFRAME [{kf['timestamp_str']}]: {kf['title']}\n\n"
        
        if i < len(thumbnails):
            thumbnail_url = thumbnails[i]
            youtube_link = f"https://www.youtube.com/watch?v={video_id}&t={kf['timestamp']}"
            markdown += f"![Keyframe at {kf['timestamp_str']}]({thumbnail_url})\n\n"
            markdown += f"[▶️ Watch this section on YouTube]({youtube_link})\n\n"
        
        markdown += f"{kf['summary']}\n\n"
        markdown += "---\n\n"
    
    return markdown

def display_multimodal_fusion_interactive(highlights, fused_df, video_id, target_lang):
    """
    Display multimodal fusion results with visual/audio metrics.
    """
    st.subheader("🎬 Multimodal Fusion Analytics")
    
    st.markdown("### Visual + Audio + Text Importance")
    chart_data = fused_df.copy()
    
    chart_data = chart_data.rename(columns={
        'visual_score': 'Visual Change',
        'audio_score': 'Audio Emphasis',
        'text_rank': 'Text Importance'
    })
    st.line_chart(chart_data.set_index('start')[['Visual Change', 'Audio Emphasis', 'Text Importance']])
    
    st.info("💡 We've fused scene changes, audio volume, and text patterns to find these highlights.")
    
    st.markdown("---")
    st.markdown(f"### 🎯 Multimodal Top Highlights ({target_lang})")
    
    markdown_output = f"# Multimodal Fusion Summary\n\n"
    
    for i, h in enumerate(highlights):
        with st.expander(f"⭐ Highlight {i+1}: {format_timestamp(h['timestamp'])} (Score: {h['score']:.1f})", expanded=(i==0)):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(f"http://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                st.markdown(f"**[Watch at {format_timestamp(h['timestamp'])}](https://www.youtube.com/watch?v={video_id}&t={h['timestamp']}s)**")
            
            with col2:
                m = h['metrics']
                st.progress(h['score']/100, text=f"Overall Fusion Score: {h['score']:.1f}%")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Visual", f"{m['visual']:.0f}%")
                c2.metric("Audio", f"{m['audio']:.0f}%")
                c3.metric("Text", f"{m['text']:.0f}%")
                
                summary_text = h['text']
                if target_lang != "English":
                    summary_text = translate_text(summary_text, target_lang)
                
                st.write(summary_text)
                markdown_output += f"## Highlight {i+1}: {format_timestamp(h['timestamp'])}\n"
                markdown_output += f"**Score: {h['score']:.1f}%**\n\n"
                markdown_output += f"{summary_text}\n\n"
                markdown_output += f"--- \n"
                
    return markdown_output

def display_engagement_fusion_interactive(highlights, engagement_df, video_id, target_lang):
    """
    Display engagement fusion results with interactive charts.
    """
    st.subheader("📊 Engagement Analytics Fusion")
    
    # Visualization
    st.markdown("### Multimodal Engagement Trends")
    # Prepare data for chart
    chart_data = engagement_df.copy()
    
    # Add a column to mark selected highlights for visualization
    chart_data['Selected Highlights'] = 0
    highlight_times = [h['timestamp'] for h in highlights]
    for ht in highlight_times:
        # Find index closest to highlight time
        idx = (chart_data['timestamp'] - ht).abs().idxmin()
        chart_data.at[idx, 'Selected Highlights'] = 100 # Visual spike
        
    chart_data = chart_data.rename(columns={
        'retention': 'Viewer Retention',
        'sentiment': 'Sentiment Density',
        'interaction': 'Interaction Peaks'
    })
    st.line_chart(chart_data.set_index('timestamp')[['Viewer Retention', 'Sentiment Density', 'Interaction Peaks', 'Selected Highlights']])
    
    st.info("💡 The graph above shows how we fused different signals to find the most 'important' moments.")
    
    st.markdown("---")
    st.markdown(f"### 🎯 Fusion-based Top Highlights ({target_lang})")
    
    markdown_output = f"# Engagement-Aware Summary (Fusion-Based)\n\n"
    
    for i, h in enumerate(highlights):
        is_spike = h.get('is_spike', False)
        spike_badge = " 🔥 **Retention Spike!**" if is_spike else ""
        
        with st.expander(f"{'🔥' if is_spike else '⭐'} Highlight {i+1}: {format_timestamp(h['timestamp'])} (Score: {h['score']:.1f}){spike_badge}", expanded=(i==0)):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(f"http://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                st.markdown(f"**[Watch at {format_timestamp(h['timestamp'])}](https://www.youtube.com/watch?v={video_id}&t={h['timestamp']}s)**")
            
            with col2:
                # Metrics breakdown
                m = h['metrics']
                st.progress(h['score']/100, text=f"Overall Fusion Score: {h['score']:.1f}%")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Retention", f"{m['retention']:.0f}%")
                c2.metric("Sentiment", f"{m['sentiment']:.0f}%")
                c3.metric("TextRank", f"{m['text_rank']:.0f}%")
                
                # Summary text
                summary_text = h['text']
                if target_lang != "English":
                    summary_text = translate_text(summary_text, target_lang)
                
                st.write(summary_text)
                markdown_output += f"## Highlight {i+1}: {format_timestamp(h['timestamp'])}\n"
                markdown_output += f"**Score: {h['score']:.1f}%**\n\n"
                markdown_output += f"{summary_text}\n\n"
                markdown_output += f"--- \n"
                
    return markdown_output


def display_textrank_interactive(keyframes, video_id, target_lang, engagement_df=None, engagement_highlights=None):
    if 'textrank_translations' not in st.session_state:
        st.session_state['textrank_translations'] = {}
        
    thumbnails = get_diverse_thumbnails(video_id, len(keyframes))
    full_markdown = ""
    
    st.markdown(f"## 📋 Detailed Notes by Keyframes (TextRank) - {target_lang}")
    
    # --- 1. Detailed Content Analysis (TextRank Keyframes) ---
    st.markdown("### 🔍 Detailed Content Analysis")
    full_markdown += "# TextRank Detailed Notes\n\n"
    
    for i, kf in enumerate(keyframes):
        timestamp_str = kf['timestamp_str']
        title = kf['title']
        summary = kf['summary']
        timestamp = kf['timestamp']
        
        # Enhanced Spike Match Logic: Check for proximity to fusion highlights
        is_spike = False
        if engagement_highlights:
            is_spike = any(abs(timestamp - h['timestamp']) < 15 for h in engagement_highlights)
        elif engagement_df is not None:
             eng_idx = (engagement_df['timestamp'] - timestamp).abs().idxmin()
             is_spike = bool(engagement_df.iloc[eng_idx]['is_spike'])
        
        # Unique ID for this keyframe translation
        kf_id = f"{video_id}_{timestamp}"
        
        if target_lang != "English":
            if kf_id not in st.session_state['textrank_translations']:
                with st.spinner(f"Translating segment to {target_lang}..."):
                    st.session_state['textrank_translations'][kf_id] = translate_text(summary, target_lang)
            display_summary = st.session_state['textrank_translations'][kf_id]
        else:
            display_summary = summary
        
        # Display Keyframe Header
        header_prefix = "🔥 " if is_spike else ""
        spike_badge = " — 🎯 **High Interest Moment!**" if is_spike else ""
        st.markdown(f"### {header_prefix}KEYFRAME [{timestamp_str}]: {title}{spike_badge}")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if i < len(thumbnails):
                st.image(thumbnails[i], caption=f"Keyframe at {timestamp_str}", use_container_width=True)
            st.markdown(f"[▶️ Watch on YouTube](https://www.youtube.com/watch?v={video_id}&t={timestamp})")

        with col2:
            if is_spike:
                st.info("🔥 **Content Insight:** This section aligns with a peak in viewer interest and sentiment.")
            st.markdown(display_summary)
            
        st.markdown("---")
        
        # Assemble Markdown for Download
        spike_md = " 🔥 **(High Interest)**" if is_spike else ""
        full_markdown += f"## KEYFRAME [{timestamp_str}]: {title}{spike_md}\n\n"
        if i < len(thumbnails):
            full_markdown += f"![Keyframe at {timestamp_str}]({thumbnails[i]})\n\n"
        full_markdown += f"[▶️ Watch on YouTube](https://www.youtube.com/watch?v={video_id}&t={timestamp})\n\n"
        full_markdown += f"{display_summary}\n\n"
        full_markdown += "---\n\n"

    # --- 2. Top Engagement Spikes (Fusion-Based) ---
    if engagement_highlights:
        st.markdown("### 🎯 Top Engagement Spikes (High Interest)")
        full_markdown += "# Top Engagement Highlights\n\n"
        
        for i, h in enumerate(engagement_highlights):
            with st.expander(f"🔥 Highlight {i+1}: {format_timestamp(h['timestamp'])} (Engagement Score: {h['score']:.1f}%)", expanded=(i==0)):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(f"http://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
                    st.markdown(f"**[Watch at {format_timestamp(h['timestamp'])}](https://www.youtube.com/watch?v={video_id}&t={h['timestamp']}s)**")
                
                with col2:
                    m = h['metrics']
                    st.progress(h['score']/100, text=f"Overall Interest Score: {h['score']:.1f}%")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Retention", f"{m['retention']:.0f}%")
                    c2.metric("Sentiment", f"{m['sentiment']:.0f}%")
                    c3.metric("TextRank", f"{m['text_rank']:.0f}%")
                    
                    highlight_text = h['text']
                    if target_lang != "English":
                        highlight_text = translate_text(highlight_text, target_lang)
                    st.write(highlight_text)
                    
                    full_markdown += f"## Spike {i+1}: {format_timestamp(h['timestamp'])}\n"
                    full_markdown += f"**Score: {h['score']:.1f}%**\n\n"
                    full_markdown += f"{highlight_text}\n\n"
        st.markdown("---")

    # --- 3. Integrated Engagement Analytics (Graph) ---
    if engagement_df is not None:
        st.markdown("### 📊 Audience Engagement & Retention")
        chart_data = engagement_df.copy()
        chart_data['Highlights'] = 0
        
        # Mark both TextRank and Fusion highlights on the chart
        all_highlights = [kf['timestamp'] for kf in keyframes]
        if engagement_highlights:
            all_highlights.extend([h['timestamp'] for h in engagement_highlights])
            
        for ht in all_highlights:
            idx = (chart_data['timestamp'] - ht).abs().idxmin()
            chart_data.at[idx, 'Highlights'] = 100
            
        chart_data = chart_data.rename(columns={
            'retention': 'Viewer Retention',
            'sentiment': 'Sentiment Density',
            'interaction': 'Interaction Peaks'
        })
        st.line_chart(chart_data.set_index('timestamp')[['Viewer Retention', 'Sentiment Density', 'Interaction Peaks', 'Highlights']])
        st.info("💡 Peaks in the graph (Highlights) show where audience engagement meets key content transitions.")

    return full_markdown

# --------- Login/Registration UI ---------

def show_login_page():

    st.title("🎥 YouTube Keyframe Summarizer")
    st.markdown("### Powered by Gemini Flash + TextRank + PCA")
    
    # Check if database is configured
    if not DATABASE_URL:
        st.warning("⚠️ Database not configured. Authentication disabled.")
        st.info("To enable login, set DATABASE_URL in your .env file")
        if st.button("Continue without login", type="primary"):
            st.session_state['logged_in'] = True
            st.session_state['username'] = 'Guest'
            st.rerun()
        return
    
    st.subheader("Login or Register to Continue")
    
    # Initialize database
    if not init_database():
        st.error("Failed to connect to database.")
        if st.button("Continue without login", type="secondary"):
            st.session_state['logged_in'] = True
            st.session_state['username'] = 'Guest'
            st.rerun()
        return
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary"):
            if login_username and login_password:
                with st.spinner("Authenticating..."):
                    success, user_data = authenticate_user(login_username, login_password)
                    if success:
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = login_username
                        st.session_state['user_data'] = user_data
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
            else:
                st.warning("Please enter both username and password")
    
    with tab2:
        st.subheader("Register")
        reg_username = st.text_input("Choose Username", key="reg_username")
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Choose Password", type="password", key="reg_password")
        reg_password_confirm = st.text_input("Confirm Password", type="password", key="reg_password_confirm")
        
        if st.button("Register", type="primary"):
            if reg_username and reg_email and reg_password and reg_password_confirm:
                if reg_password != reg_password_confirm:
                    st.error("❌ Passwords do not match")
                elif len(reg_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                elif not re.match(r"[^@]+@[^@]+\.[^@]+", reg_email):
                    st.error("❌ Invalid email format")
                elif check_username_exists(reg_username):
                    st.error("❌ Username already exists")
                else:
                    with st.spinner("Creating account..."):
                        success, message = register_user(reg_username, reg_password, reg_email)
                        if success:
                            st.success("✅ " + message)
                            st.info("Please login with your credentials")
                        else:
                            st.error(message)
            else:
                st.warning("Please fill in all fields")

# --------- Main App UI ---------

def show_main_app():

    st.title("🎥 YouTube Transcript Summarizer")
    st.markdown("### Powered by Gemini Flash + TextRank + PCA")
    
    # Create header with user info and logout
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"Welcome, {st.session_state.get('username', 'User')}! 👋")
    with col2:
        if st.button("Logout", type="secondary"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.session_state['user_data'] = None
            # Clear analysis state on logout
            for key in ['transcript_text', 'transcript_timestamps', 'gemini_result', 'textrank_result', 'last_video_link', 'current_video_id', 'target_language']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    st.markdown("---")
    
    # Initialize session state for analysis results if not present
    if 'transcript_text' not in st.session_state:
        st.session_state['transcript_text'] = None
    if 'transcript_timestamps' not in st.session_state:
        st.session_state['transcript_timestamps'] = None
    if 'gemini_result' not in st.session_state:
        st.session_state['gemini_result'] = None
    if 'textrank_result' not in st.session_state:
        st.session_state['textrank_result'] = None
    if 'engagement_result' not in st.session_state:
        st.session_state['engagement_result'] = None
    if 'engagement_df' not in st.session_state:
        st.session_state['engagement_df'] = None
    if 'multimodal_result' not in st.session_state:
        st.session_state['multimodal_result'] = None
    if 'multimodal_df' not in st.session_state:
        st.session_state['multimodal_df'] = None
    if 'last_video_link' not in st.session_state:
        st.session_state['last_video_link'] = ""
    if 'current_video_id' not in st.session_state:
        st.session_state['current_video_id'] = None
    if 'target_language' not in st.session_state:
        st.session_state['target_language'] = "English"
    if 'ranking_model' not in st.session_state:
        st.session_state['ranking_model'] = "Balanced"
    if 'auto_detected_model' not in st.session_state:
        st.session_state['auto_detected_model'] = None
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Language Selection
        languages = ["English", "Telugu", "Hindi", "Spanish", "French", "German", "Tamil", "Kannada", "Malayalam"]
        selected_language = st.selectbox(
            "Select Output Language",
            languages,
            index=languages.index(st.session_state.get('target_language', "English"))
        )
        
        # Check if language changed
        if selected_language != st.session_state.get('target_language', "English"):
            st.session_state['target_language'] = selected_language
            # Clear existing results to trigger re-generation/translation
            st.session_state['gemini_result'] = None
            st.session_state['textrank_result'] = None
            st.session_state['textrank_translations'] = {}
            # Clear chat history on language/video change? Maybe keep it.
            st.rerun()

        summarization_method = st.radio(
            "Summarization Method",
            ["Gemini AI (Abstractive)", "TextRank (Extractive)", "Multimodal Fusion (Visual+Audio)", "Hybrid (All)"],
            help="Choose between AI-based, TextRank-based, Visual+Audio-Aware summarization"
        )
        
        st.markdown("---")
        
        if "TextRank" in summarization_method or "Hybrid" in summarization_method:
            st.subheader("🔍 TextRank Settings")
            use_pca = st.checkbox("Apply PCA Dimensionality Reduction", value=True)
            
            if use_pca:
                pca_components = st.slider(
                    "PCA Components",
                    min_value=10,
                    max_value=200,
                    value=50,
                    step=10,
                    help="Number of principal components to retain"
                )
            else:
                pca_components = None
            
            num_keyframes = st.slider(
                "Number of Keyframes",
                min_value=3,
                max_value=10,
                value=7,
                help="Number of keyframes to extract"
            )
        st.markdown("---")
        
        st.subheader("🔥 Engagement Model")
        model_options = ["Auto-Detect", "Balanced", "Engagement-Heavy", "Emotion-Aware"]
        selected_model = st.selectbox(
            "Ranking Priority",
            model_options,
            index=model_options.index(st.session_state.get('ranking_model', "Auto-Detect")),
            help="Balanced: stable; Engagement-Heavy: viral/controversy; Emotion-Aware: storytelling"
        )
        
        if selected_model != st.session_state.get('ranking_model', "Auto-Detect"):
            st.session_state['ranking_model'] = selected_model
            # Logic will handle auto-detect later
            st.session_state['engagement_result'] = None # Re-run engagement
            st.rerun()

        st.markdown("---")
        
        if not nltk_ready:
            st.warning("⚠️ NLTK not fully loaded. TextRank may have reduced accuracy.")
            
        st.info("💡 **TextRank** uses graph-based ranking to extract key sentences. **PCA** reduces dimensionality for better performance.")
    
        # --- History Section in Sidebar ---
        if st.session_state.get('logged_in'):
            st.markdown("---")
            with st.expander("📜 History"):
                user_data = st.session_state.get('user_data')
                if user_data:
                    history = get_user_history(user_data.get('id') if isinstance(user_data, dict) else user_data[0]) 
                    # user_data might be dict or tuple depending on fetch
                    # authenticate_user returns dict(user_data) so it should be dict.
                    # But let's be safe. user_data is dict from authenticate_user.
                    
                    if not history:
                        st.info("No history found.")
                    else:
                        for item in history:
                            # Create a clearer label
                            label = f"{item.get('video_title', 'Video')} ({item.get('created_at').strftime('%Y-%m-%d %H:%M')})"
                            if st.button(label, key=f"hist_{item['id']}", help=item.get('video_url')):
                                # Load history item
                                st.session_state['transcript_text'] = item['transcript']
                                # For timestamps, we might need to re-parse or store them. 
                                # We stored transcript text but not the structured timestamps in DB for simplicity in this plan.
                                # So we might need to re-extract details if we want timestamps.
                                # However, the plan said "transcript TEXT".
                                # If we want full functionality, we need to re-fetch timestamps or store json.
                                # Let's try to re-fetch if transcript matches, or just set transcript and let user re-process?
                                # No, the point is to avoid re-processing. 
                                # But we didn't store structured timestamps in DB. 
                                # Quick fix: We can try to re-extract timestamps from transcript text if they were embedded? No.
                                # We should rely on caching or just re-fetch timestamps since that's fast (unlike Gemini).
                                # But Gemini result IS stored.
                                
                                st.session_state['transcript_timestamps'] = None # Re-fetch if needed or handle gracefully
                                st.session_state['gemini_result'] = item['summary'] if "KEYFRAME" in item['summary'] else None
                                st.session_state['textrank_result'] = None # We didn't distinguish explicitly in DB schema "summary" field meaning.
                                # The schema has 'summary' column.
                                # We need to check if it looks like Gemini or TextRank or just put it in a generic place?
                                # If it has "## KEYFRAME", it's likely Gemini.
                                
                                # Creating a simple "History View" mode might be better than full state restoration if data is partial.
                                # But let's try to restore as much as possible.
                                st.session_state['last_video_link'] = item['video_url']
                                st.session_state['current_video_id'] = extract_video_id(item['video_url'])
                                st.session_state['history_loaded'] = True
                                # Update the text input value
                                st.session_state['youtube_url'] = item['video_url']
                                st.rerun()

    st.markdown("### Get detailed notes with keyframe timestamps")
    
    youtube_link = st.text_input("🔗 Enter YouTube Video Link:", placeholder="https://www.youtube.com/watch?v=...", key="youtube_url")

    if youtube_link:
        vid = extract_video_id(youtube_link)
        if vid:
            st.image(f"http://img.youtube.com/vi/{vid}/0.jpg", use_container_width=True)

    # Check if we should process
    process_button = st.button("📝 Get Detailed Notes with Keyframes", type="primary")
    
    # Logic to handle processing or displaying cached results
    if youtube_link:
        vid = extract_video_id(youtube_link)
        
        if vid:
            # If video changed, clear cache
            if youtube_link != st.session_state['last_video_link']:
                st.session_state['transcript_text'] = None
                st.session_state['transcript_timestamps'] = None
                st.session_state['gemini_result'] = None
                st.session_state['textrank_result'] = None
                st.session_state['engagement_df'] = None
                st.session_state['multimodal_result'] = None
                st.session_state['multimodal_df'] = None
                st.session_state['last_video_link'] = youtube_link
                st.session_state['current_video_id'] = vid
            
            # If button clicked, process
            if process_button:
                if not youtube_link:
                    st.warning("Please enter a YouTube video link first")
                else:
                    with st.spinner("🔍 Extracting transcript..."):
                        # Fetch transcript only if not cached
                        if not st.session_state['transcript_text']:
                            transcript_text, transcript_with_timestamps = extract_transcript_details(youtube_link)
                            st.session_state['transcript_text'] = transcript_text
                            st.session_state['transcript_timestamps'] = transcript_with_timestamps
                        
                        if not st.session_state['transcript_text'] and "Multimodal" not in summarization_method:
                            st.error("❌ Could not extract video ID or transcript from the provided link.")
                        elif not st.session_state['transcript_text'] and "Multimodal" in summarization_method:
                            st.info("ℹ️ No transcript found. Proceeding with Multimodal Fusion (Visual + Audio + OCR) only.")
            
            # --- Auto-load timestamps if missing but transcript exists (e.g. from history) ---
            if st.session_state.get('history_loaded') and not st.session_state['transcript_timestamps']:
                 with st.spinner("🔄 Restoring video details..."):
                     _, transcript_with_timestamps = extract_transcript_details(youtube_link)
                     st.session_state['transcript_timestamps'] = transcript_with_timestamps
                     st.session_state.pop('history_loaded', None) # Clear flag

            # Display results if transcript is available or Multimodal method is selected
            if st.session_state['transcript_text'] or "Multimodal" in summarization_method:
                transcript_text = st.session_state['transcript_text']
                transcript_with_timestamps = st.session_state['transcript_timestamps']
                target_lang = st.session_state.get('target_language', "English")
                
                # Check transcript length if it exists
                if transcript_text:
                    word_count = len(transcript_text.split())
                    st.info(f"📊 Transcript extracted: ~{word_count} words | Output Language: {target_lang}")
                
                # Apply PCA analysis if transcript exists and requested
                if use_pca and transcript_text:
                    with st.spinner("🔬 Performing PCA analysis..."):
                        pca_results, pca_error = apply_pca_to_transcript(
                            transcript_text,
                            n_components=pca_components if pca_components else 100
                        )
                        
                        if pca_results:
                            st.sidebar.success(f"✅ PCA Analysis Complete!")
                            st.sidebar.metric("Optimal Components", pca_results['optimal_components'])
                            st.sidebar.metric("Variance Retained (95%)", f"{pca_results['total_variance_95']*100:.1f}%")
                
                # Generate summaries if missing for selected method
                
                # TextRank Generation (Requires transcript)
                if ("TextRank" in summarization_method or "Hybrid" in summarization_method) and not st.session_state['textrank_result'] and transcript_with_timestamps:
                     with st.spinner("🤖 Applying TextRank algorithm..."):
                        keyframes = extract_keyframes_with_textrank(
                            transcript_with_timestamps,
                            num_keyframes=num_keyframes
                        )
                        st.session_state['textrank_result'] = keyframes
                
                # Engagement Fusion Generation (Internal for Spikes & Highlights)
                if ("TextRank" in summarization_method or "Hybrid" in summarization_method) and (st.session_state['engagement_df'] is None or st.session_state['engagement_result'] is None) and transcript_with_timestamps:
                     with st.spinner("📊 Fusing Engagement Highlights..."):
                        # Resolve model type
                        model_to_use = st.session_state.get('ranking_model', "Balanced")
                        if model_to_use == "Auto-Detect":
                            model_to_use = st.session_state.get('auto_detected_model', "Balanced")
                        
                        st.sidebar.info(f"🚀 Using Model: **{model_to_use}**")
                        
                        highlights, eng_df = get_engagement_fusion_summary(
                            transcript_with_timestamps,
                            num_keyframes=num_keyframes,
                            model_type=model_to_use.lower().replace("-", "_")
                        )
                        st.session_state['engagement_result'] = highlights
                        st.session_state['engagement_df'] = eng_df
                
                # Multimodal Fusion Generation
                if ("Multimodal" in summarization_method or "Hybrid" in summarization_method) and not st.session_state['multimodal_result']:
                     with st.spinner("🎬 Analyzing Visual + Audio + OCR peaks..."):
                        highlights, multi_df = get_multimodal_fusion_summary(
                            youtube_link,
                            transcript_with_timestamps,
                            num_keyframes=num_keyframes
                        )
                        st.session_state['multimodal_result'] = highlights
                        st.session_state['multimodal_df'] = multi_df
                
                # Gemini Generation (Requires transcript)
                if ("Gemini" in summarization_method or "Hybrid" in summarization_method) and not st.session_state['gemini_result'] and transcript_text:
                    with st.spinner(f"🤖 Analyzing content with Gemini AI in {target_lang}..."):
                        keyframe_notes = generate_gemini_content(transcript_text, gemini_prompt, target_lang)
                        st.session_state['gemini_result'] = keyframe_notes
                        
                        # Save to history if logged in
                        if st.session_state.get('logged_in') and keyframe_notes:
                             user_id = st.session_state['user_data']['id']
                             video_title = get_video_title(youtube_link)
                             save_history(user_id, youtube_link, video_title, keyframe_notes, transcript_text)
                             st.toast("✅ Saved in History!")
                             # Force reload to update sidebar history
                             import time
                             time.sleep(1) # Give a moment for toast
                             st.rerun()

                # Display Logic
                if summarization_method == "TextRank (Extractive)":
                    keyframes = st.session_state['textrank_result']
                    if keyframes:
                        # Translate if needed (TextRank output is usually English from extract)
                        # We translate the FINAL markdown for display
                        st.success("✅ TextRank analysis ready!")
                        
                        # New Interactive Display - INTEGRATED
                        eng_df = st.session_state.get('engagement_df')
                        eng_highlights = st.session_state.get('engagement_result')
                        keyframe_markdown = display_textrank_interactive(keyframes, vid, target_lang, eng_df, eng_highlights)
                        
                        # Save TextRank result to history (as markdown)
                        if st.session_state.get('logged_in') and keyframe_markdown:
                             user_id = st.session_state['user_data']['id']
                             # Check if we just saved to avoid infinite loop or duplicate
                             # Ideally we should check if recent history matches current video
                             # But simpler: only save if not loaded from history
                             if not st.session_state.get('history_loaded', False):
                                 # We need to construct a cleaner markdown for history storage (without interactive buttons code essentially)
                                 # Actually, saving the generated markdown is fine, but interactive buttons won't work from history text.
                                 # Let's save a clean version using format_textrank_keyframes (which we removed? No, definition is still there just not used in display)
                                 # Wait, I removed format_textrank_keyframes usage but let's check if function still exists? I modified usage.
                                 # Function definition is lines 765-783.
                                 clean_markdown = format_textrank_keyframes(keyframes, vid)
                                 video_title = get_video_title(youtube_link)
                                 
                                 # Check if we already saved this session
                                 if 'last_saved_video' not in st.session_state or st.session_state['last_saved_video'] != vid:
                                     save_history(user_id, youtube_link, video_title, clean_markdown, transcript_text)
                                     st.session_state['last_saved_video'] = vid
                                     st.toast("✅ TextRank Result Saved to History!")
                                     import time
                                     time.sleep(1)
                                     st.rerun()

                        st.markdown("---")
                        st.markdown("### 📥 Download Your Notes")
                        st.download_button(
                            label=f"📄 Download TextRank Notes ({target_lang})",
                            data=keyframe_markdown,
                            file_name=f"textrank_notes_{target_lang}.md",
                            mime="text/markdown",
                        )
            
                elif summarization_method == "Engagement Fusion (Multimodal)":
                    pass # Handled within TextRank or Hybrid now
            
                elif summarization_method == "Multimodal Fusion (Visual+Audio)":
                    highlights = st.session_state['multimodal_result']
                    multi_df = st.session_state['multimodal_df']
                    if highlights and multi_df is not None:
                        st.success("✅ Multimodal Visual + Audio Fusion ready!")
                        multi_markdown = display_multimodal_fusion_interactive(highlights, multi_df, vid, target_lang)
                        
                        st.download_button(
                            label=f"📄 Download Multimodal Fusion Notes ({target_lang})",
                            data=multi_markdown,
                            file_name=f"multimodal_fusion_notes_{target_lang}.md",
                            mime="text/markdown",
                        )
                    else:
                        st.warning("⚠️ Multimodal analysis completed but no significant highlights were found. This can happen if the video is very short or has very few visual/audio changes.")
                        if st.button("🔄 Retry with lower sensitivity"):
                            st.session_state['multimodal_result'] = None
                            st.session_state['multimodal_df'] = None
                            st.rerun()
            
                elif summarization_method == "Gemini AI (Abstractive)":
                    keyframe_notes = st.session_state['gemini_result']
                    if keyframe_notes:
                        timestamps = extract_timestamps_from_notes(keyframe_notes)
                        if not timestamps:
                            timestamps = estimate_keyframe_timestamps(transcript_with_timestamps)

                        st.success("✅ Gemini AI analysis ready!")
                        st.markdown(f"## 📋 Detailed Notes by Keyframes (Gemini AI) - {target_lang}")
                        
                        # Note: Gemini result is already in target language from generation
                        display_keyframe_notes_with_thumbnails(keyframe_notes, vid, timestamps)

                        enhanced_markdown = generate_markdown_with_thumbnails(keyframe_notes, vid, timestamps)

                        st.markdown("---")
                        st.markdown("### 📥 Download Your Notes")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.download_button(
                                label=f"📄 Download Basic Notes ({target_lang})",
                                data=keyframe_notes,
                                file_name=f"gemini_notes_{target_lang}.md",
                                mime="text/markdown",
                            )
                        with col2:
                            st.download_button(
                                label=f"🖼️ Download Notes with Thumbnails ({target_lang})",
                                data=enhanced_markdown,
                                file_name=f"gemini_notes_with_thumbnails_{target_lang}.md",
                                mime="text/markdown",
                            )
            
                else:  # Hybrid (All) mode
                    st.success("✅ Comprehensive Hybrid analysis ready!")
                    
                    # Display side by side
                    tab1, tab2, tab3, tab4 = st.tabs(["🔍 TextRank", "🤖 Gemini AI", "📊 Engagement Fusion", "🎬 Multimodal Fusion"])
                    
                    with tab1:
                        st.markdown(f"## 📋 TextRank Summary ({target_lang})")
                        keyframes = st.session_state['textrank_result']
                        if keyframes:
                            eng_df = st.session_state.get('engagement_df')
                            eng_highlights = st.session_state.get('engagement_result')
                            keyframe_markdown = display_textrank_interactive(keyframes, vid, target_lang, eng_df, eng_highlights)
                            st.download_button(
                                label="Download TextRank Notes",
                                data=keyframe_markdown,
                                file_name=f"textrank_notes_{target_lang}.md",
                                mime="text/markdown",
                                key="download_textrank_hybrid"
                            )
                    
                    with tab2:
                        st.markdown(f"## 📋 Gemini AI Summary ({target_lang})")
                        keyframe_notes = st.session_state['gemini_result']
                        if keyframe_notes:
                            timestamps = extract_timestamps_from_notes(keyframe_notes)
                            if not timestamps:
                                timestamps = estimate_keyframe_timestamps(transcript_with_timestamps)
                            display_keyframe_notes_with_thumbnails(keyframe_notes, vid, timestamps)
                            st.download_button(
                                label="Download Gemini Notes",
                                data=keyframe_notes,
                                file_name=f"gemini_notes_{target_lang}.md",
                                mime="text/markdown",
                                key="download_gemini_hybrid"
                            )

                    with tab3:
                        highlights = st.session_state['engagement_result']
                        eng_df = st.session_state['engagement_df']
                        if highlights and eng_df is not None:
                            fusion_markdown = display_engagement_fusion_interactive(highlights, eng_df, vid, target_lang)
                            st.download_button(
                                label="Download Fusion Notes",
                                data=fusion_markdown,
                                file_name=f"engagement_fusion_notes_{target_lang}.md",
                                mime="text/markdown",
                                key="download_fusion_hybrid"
                            )

                    with tab4:
                        highlights = st.session_state['multimodal_result']
                        multi_df = st.session_state['multimodal_df']
                        if highlights and multi_df is not None:
                            multi_markdown = display_multimodal_fusion_interactive(highlights, multi_df, vid, target_lang)
                            st.download_button(
                                label="Download Multimodal Notes",
                                data=multi_markdown,
                                file_name=f"multimodal_fusion_notes_{target_lang}.md",
                                mime="text/markdown",
                                key="download_multimodal_hybrid"
                            )
                    
                    # --- Related Content Section ---
                    st.markdown("---")
                    with st.expander("🔎 Related Content & Suggestions", expanded=True):
                        col1, col2 = st.columns(2)
                        
                        # 1. History-based Suggestions
                        with col1:
                            st.subheader("📚 From Your History")
                            if st.session_state.get('logged_in') and transcript_text:
                                with st.spinner("Finding related videos..."):
                                    related_videos = get_related_videos_from_history(
                                        vid, 
                                        transcript_text, 
                                        st.session_state['user_data']['id']
                                    )
                                    
                                if related_videos:
                                    for video in related_videos:
                                        st.markdown(f"**[{video['video_title']}]({video['video_url']})**")
                                        st.caption(f"Similarity: {video['similarity_score']:.2f}")
                                else:
                                    st.info("No similar videos found in your history.")
                            else:
                                st.info("Login to see related videos from your history.")
                                
                        # 2. AI-based Topic Suggestions & External Content
                        with col2:
                            st.subheader("🌐 Explore More on YouTube")
                            
                            # Generate metadata if not present (Combined Call)
                            if 'related_topics' not in st.session_state:
                                with st.spinner("Generating suggestions..."):
                                    # Use optimized single call
                                    cat, tops = analyze_video_metadata(transcript_text)
                                    st.session_state['video_category'] = cat
                                    st.session_state['related_topics'] = tops
                                    
                                    # Auto-detect ranking model based on category
                                    # Balanced: Academic, Education, Tech, Cooking
                                    # Engagement-Heavy: News, Gaming, Business, Sports, Politics, Debates
                                    # Emotion-Aware: Motivation, Storytelling, Movies, Speeches, Travel
                                    
                                    cat_lower = cat.lower()
                                    if any(keyword in cat_lower for keyword in ['motivation', 'travel', 'health', 'movie', 'speech']):
                                        detected = "Emotion-Aware"
                                    elif any(keyword in cat_lower for keyword in ['gaming', 'news', 'business', 'sports', 'debate', 'politics']):
                                        detected = "Engagement-Heavy"
                                    else:
                                        detected = "Balanced"
                                    
                                    st.session_state['auto_detected_model'] = detected
                                    
                                    # If currently in Auto-Detect, we might need a rerun to apply this to Engagement Fusion
                                    if st.session_state.get('ranking_model') == "Auto-Detect":
                                        st.session_state['engagement_result'] = None # Trigger re-calculate with new model
                                        st.rerun()
                            
                            # Display Categories / Recently Uploaded
                            category = st.session_state.get('video_category', 'General')
                            st.markdown(f"**Category:** {category}")
                            
                            if 'recent_videos' not in st.session_state:
                                query = f"latest {category} videos"
                                st.session_state['recent_videos'] = get_youtube_search_results(query, 3)
                            
                            # Display Recently Uploaded in Category
                            st.markdown(f"**🆕 Recently Uploaded in {category}**")
                            recent_videos = st.session_state.get('recent_videos', [])
                            if recent_videos:
                                for vid in recent_videos:
                                    # Create a small card-like layout
                                    c1, c2 = st.columns([1, 2])
                                    with c1:
                                        st.image(vid['thumbnail'], use_container_width=True)
                                    with c2:
                                        st.markdown(f"[{vid['title']}]({vid['link']})")
                                        st.caption(f"{vid['views']} • {vid['published']}")
                            
                            st.markdown("---")
                                    
                            # Display Enhanced Topics
                            st.markdown("**🔍 Related Topics**")
                            topics = st.session_state.get('related_topics', [])
                            if topics:
                                for topic in topics:
                                    with st.expander(f"📌 {topic}"):
                                        # Initializing search on click would be slow, better to just link or fetch on expand?
                                        # Let's fetch one top result for the topic
                                        top_result = get_youtube_search_results(topic, 1)
                                        if top_result:
                                            v = top_result[0]
                                            c1s, c2s = st.columns([1, 2])
                                            with c1s:
                                                st.image(v['thumbnail'], use_container_width=True)
                                            with c2s:
                                                st.markdown(f"[{v['title']}]({v['link']})")
                                                st.caption(f"{v['views']} • {v['published']}")
                                            
                                        search_url = f"https://www.youtube.com/results?search_query={topic.replace(' ', '+')}"
                                        st.markdown(f"[See all results for '{topic}' on YouTube]({search_url})")
                            else:
                                st.info("Could not generate topics.")
                    
                    # --- Q&A Chatbot Section ---
                    st.markdown("---")
                    st.subheader("💬 Chat with this Video")
                    
                    # Initialize chat history
                    if 'chat_history' not in st.session_state:
                        st.session_state['chat_history'] = []
                    
                    # Display chat messages from history on app rerun
                    for message in st.session_state['chat_history']:
                        with st.chat_message(message["role"]):
                            st.markdown(message["content"])
                    
                    # React to user input
                    if prompt := st.chat_input("Ask a question about the video..."):
                        # Display user message in chat message container
                        st.chat_message("user").markdown(prompt)
                        # Add user message to chat history
                        st.session_state['chat_history'].append({"role": "user", "content": prompt})
                        
                        # Display assistant response in chat message container
                        with st.chat_message("assistant"):
                            with st.spinner("Thinking..."):
                                response = ask_about_video(transcript_text, prompt)
                                st.markdown(response)
                        
                        # Add assistant response to chat history
                        st.session_state['chat_history'].append({"role": "assistant", "content": response})

    
    st.markdown("---")
    st.markdown("### 📚 How to use")
    st.info("Paste a video URL, select options, and click 'Get Detailed Notes'.")

    
    with st.expander("🔬 Technical Details"):
        st.info("Powered by Gemini Flash, TextRank (TF-IDF + PageRank), and PCA.")

    
    with st.expander("🛠️ Troubleshooting"):
        st.info("If you see errors, check your .env file for GOOGLE_API_KEY and DATABASE_URL.")


# --------- Main Application Logic ---------

def main():
    st.set_page_config(
        page_title="YouTube Keyframe Summarizer - Gemini AI + TextRank", 
        layout="wide",
        page_icon="🎥"
    )
    
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    
    # Show appropriate page based on login status
    if st.session_state['logged_in']:
        show_main_app()
    else:
        show_login_page()

if __name__ == "__main__":
    main()
