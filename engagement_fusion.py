import numpy as np
import pandas as pd
import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

class EngagementFuser:
    """
    Engagement-Aware Multimodal Ranking System for Video Summarization.
    Fuses TextRank, Retention Graphs, and Sentiment Data.
    """
    
    def __init__(self, model_type='balanced', text_base_weight=0.2):
        self.model_type = model_type.lower()
        self.text_weight = text_base_weight
        
        # User defined ratios for the remaining (1 - text_base_weight)
        remaining = 1.0 - text_base_weight
        
        if self.model_type == 'engagement_heavy':
            # 40% Retention, 40% Interaction, 20% Sentiment
            self.retention_weight = remaining * 0.4
            self.interaction_weight = remaining * 0.4
            self.sentiment_weight = remaining * 0.2
        elif self.model_type == 'emotion_aware':
            # 45% Retention, 25% Interaction, 30% Sentiment
            self.retention_weight = remaining * 0.45
            self.interaction_weight = remaining * 0.25
            self.sentiment_weight = remaining * 0.3
        else: # balanced or default
            # 50% Retention, 30% Interaction, 20% Sentiment
            self.retention_weight = remaining * 0.5
            self.interaction_weight = remaining * 0.3
            self.sentiment_weight = remaining * 0.2

    def simulate_engagement_data(self, duration_sec):
        """
        Simulate YouTube-style engagement metrics for demonstration.
        - Retention: High at start, peaks at interesting moments, drops at end.
        - Sentiment: Peaks at specific timestamps.
        - Reactions: Likes/Dislikes spikes.
        """
        timestamps = np.linspace(0, duration_sec, 100)
        
        # 1. Retention Graph (Heuristic: High start, some peaks, low end)
        retention = 80 * np.exp(-timestamps / (duration_sec * 0.8)) + \
                    15 * np.sin(5 * np.pi * timestamps / duration_sec)**2 + \
                    np.random.normal(0, 2, 100)
        retention = np.clip(retention, 10, 100)
        
        # 2. Sentiment Density (Simulated peaks)
        sentiment_peaks = np.zeros_like(timestamps)
        for _ in range(3): # 3 major interesting points
            peak_idx = np.random.randint(10, 80)
            sentiment_peaks += 50 * np.exp(-((timestamps - timestamps[peak_idx])**2) / (2 * (duration_sec/20)**2))
        sentiment_density = np.clip(sentiment_peaks + np.random.normal(10, 5, 100), 0, 100)
        
        # 3. Like/Dislike Ratio Spikes
        interaction_spikes = np.random.normal(20, 10, 100)
        # Add a major "like" spike at the same place as a sentiment peak
        interaction_spikes += sentiment_peaks * 0.5
        interaction_spikes = np.clip(interaction_spikes, 0, 100)
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'retention': retention,
            'sentiment': sentiment_density,
            'interaction': interaction_spikes
        })
        return df

    def get_text_rank_scores(self, sentences):
        """Standard TextRank scoring for sentences."""
        if not sentences:
            return []
            
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(sentences)
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        nx_graph = nx.from_numpy_array(similarity_matrix)
        scores = nx.pagerank(nx_graph, max_iter=200)
        
        # Normalize scores to 0-100
        max_score = max(scores.values()) if scores else 1
        return [ (scores[i] / max_score) * 100 for i in range(len(sentences))]

    def detect_spikes(self, values, window=5, threshold=1.2):
        """
        Detect local peaks (spikes) in a series of values.
        A point is a spike if it's the max in its window and > threshold * mean.
        """
        spikes = np.zeros_like(values)
        for i in range(window, len(values) - window):
            curr = values[i]
            local_window = values[i-window : i+window+1]
            if curr == np.max(local_window) and curr > threshold * np.mean(values):
                spikes[i] = 1
        return spikes

    def fuse_metrics(self, transcript_df, engagement_df):
        """
        Multimodal Fusion Logic:
        Final_Score = (W1 * TextRank) + (W2 * Retention) + (W3 * Sentiment) + (W4 * Interaction) + Spike_Bonus
        """
        # Detect spikes in retention
        retention_values = engagement_df['retention'].values
        spikes = self.detect_spikes(retention_values)
        engagement_df['is_spike'] = spikes
        
        fused_data = []
        
        for idx, row in transcript_df.iterrows():
            t_start = row['start']
            # Find closest engagement data index
            eng_idx = (engagement_df['timestamp'] - t_start).abs().argsort()[:1].values[0]
            eng_row = engagement_df.iloc[eng_idx]
            
            retention_score = eng_row['retention']
            sentiment_score = eng_row['sentiment']
            interaction_score = eng_row['interaction']
            is_spike = bool(eng_row['is_spike'])
            text_score = row['text_rank_score']
            
            # Base Weighted Fusion
            fused_score = (
                self.retention_weight * retention_score +
                self.text_weight * text_score +
                self.sentiment_weight * sentiment_score +
                self.interaction_weight * interaction_score
            )
            
            # Apply Spike Bonus (Add 25% extra if it's a retention spike)
            if is_spike:
                fused_score += 25 
            
            fused_score = min(100, fused_score) # Cap at 100
            
            fused_data.append({
                'start': t_start,
                'end': t_start + row['duration'],
                'text': row['text'],
                'fused_score': fused_score,
                'retention': retention_score,
                'sentiment': sentiment_score,
                'interaction': interaction_score,
                'text_rank': text_score,
                'is_spike': is_spike
            })
            
        return pd.DataFrame(fused_data)

    def extract_fusion_keyframes(self, transcript_with_timestamps, num_keyframes=5):
        """Main entry point for engagement-aware keyframe extraction."""
        if not transcript_with_timestamps:
            return [], pd.DataFrame()
            
        # 1. Prepare Data
        sentences = [seg['text'] for seg in transcript_with_timestamps]
        text_scores = self.get_text_rank_scores(sentences)
        
        transcript_df = pd.DataFrame(transcript_with_timestamps)
        transcript_df['text_rank_score'] = text_scores
        
        duration = transcript_with_timestamps[-1]['start'] + transcript_with_timestamps[-1]['duration']
        engagement_df = self.simulate_engagement_data(duration)
        
        # 2. Fuse Metrics
        fused_df = self.fuse_metrics(transcript_df, engagement_df)
        
        # 3. Rank and Select Key Highlights
        # We group nearby segments to form "Keyframes"
        fused_df = fused_df.sort_values(by='fused_score', ascending=False)
        
        top_highlights = []
        seen_timestamps = []
        
        for _, row in fused_df.iterrows():
            # Avoid selecting overlapping/very close segments
            if any(abs(row['start'] - t) < (duration / (num_keyframes * 2)) for t in seen_timestamps):
                continue
                
            top_highlights.append({
                'timestamp': int(row['start']),
                'text': row['text'],
                'score': row['fused_score'],
                'is_spike': row['is_spike'],
                'metrics': {
                    'retention': row['retention'],
                    'sentiment': row['sentiment'],
                    'interaction': row['interaction'],
                    'text_rank': row['text_rank']
                }
            })
            seen_timestamps.append(row['start'])
            if len(top_highlights) >= num_keyframes:
                break
        
        # Sort by timestamp for chronological summary
        top_highlights = sorted(top_highlights, key=lambda x: x['timestamp'])
        return top_highlights, engagement_df

def get_engagement_fusion_summary(transcript_with_timestamps, num_keyframes=7, model_type='balanced'):
    """Utility function to be called from the main app."""
    fuser = EngagementFuser(model_type=model_type)
    highlights, engagement_df = fuser.extract_fusion_keyframes(transcript_with_timestamps, num_keyframes)
    return highlights, engagement_df

if __name__ == "__main__":
    # Test simulation
    fuser = EngagementFuser()
    data = fuser.simulate_engagement_data(600)
    print("Engagement Data Simulated:")
    print(data.head())
